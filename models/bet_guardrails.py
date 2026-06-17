"""Regras P0 de proteção operacional para apostas ao vivo."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings
from models.inplay_market_period import (
    effective_guardrail_market,
    is_market_blocked_by_minute,
    is_second_half_market,
    market_live_block_minute,
)
from models.wc_against_model import normalize_h2h_outcome

_EXTENSION_SOURCES = frozenset({"superbet_extension", "extension"})
_TS_FILENAME_RE = re.compile(r"(\d{8}T\d{6}Z)\.json$")


class BetGuardrailError(ValueError):
    """Violação de regra operacional (P0)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _normalize_outcome(
    market: str,
    outcome: str,
    *,
    home_team: str = "",
    away_team: str = "",
) -> str:
    """Normaliza palpite para comparação de duplicatas."""
    if market == "h2h":
        norm = normalize_h2h_outcome(outcome)
        if norm:
            return norm
        raw = (outcome or "").strip().lower()
        home_l = home_team.lower()
        away_l = away_team.lower()
        if home_l and (raw in home_l or home_l in raw):
            return "1"
        if away_l and (raw in away_l or away_l in raw):
            return "2"
        if raw in {"empate", "draw"}:
            return "X"
        return raw
    return (outcome or "").strip().lower()


def _teams_match(
    home_a: str,
    away_a: str,
    home_b: str,
    away_b: str,
) -> bool:
    from schemas.national_teams import normalize_national_team

    ah = normalize_national_team(home_a).strip().lower()
    aa = normalize_national_team(away_a).strip().lower()
    bh = normalize_national_team(home_b).strip().lower()
    ba = normalize_national_team(away_b).strip().lower()
    if ah == bh and aa == ba:
        return True
    return ah == ba and aa == bh


def _minute_from_local_event(event_id: int) -> int | None:
    """Último minuto conhecido no lake bronze para o evento."""
    root = Path(settings.lake_root) / "bronze" / "superbet" / "events" / str(event_id)
    if not root.is_dir():
        return None
    best_ts: str | None = None
    best_minute: int | None = None
    for snap_file in root.glob("*.json"):
        m = _TS_FILENAME_RE.search(snap_file.name)
        if not m:
            continue
        ts = m.group(1)
        if best_ts is not None and ts <= best_ts:
            continue
        try:
            payload = json.loads(snap_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        inplay = payload.get("inplay") or {}
        minute = inplay.get("minute")
        if minute is None:
            continue
        best_ts = ts
        best_minute = int(minute)
    return best_minute


def _minute_from_local_teams(home_team: str, away_team: str) -> int | None:
    """Busca snapshot live mais recente que combine com os times."""
    root = Path(settings.lake_root) / "bronze" / "superbet" / "events"
    if not root.is_dir():
        return None
    best: tuple[str, int] | None = None
    for event_dir in root.iterdir():
        if not event_dir.is_dir():
            continue
        for snap_file in event_dir.glob("*.json"):
            m = _TS_FILENAME_RE.search(snap_file.name)
            if not m:
                continue
            try:
                payload = json.loads(snap_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not payload.get("is_live"):
                continue
            if not _teams_match(
                home_team,
                away_team,
                str(payload.get("home_team", "")),
                str(payload.get("away_team", "")),
            ):
                continue
            inplay = payload.get("inplay") or {}
            minute = inplay.get("minute")
            if minute is None:
                continue
            ts = m.group(1)
            if best is None or ts > best[0]:
                best = (ts, int(minute))
    return best[1] if best else None


def _minute_from_superbet_api(
    *,
    superbet_event_id: int | None,
    home_team: str,
    away_team: str,
) -> int | None:
    try:
        from ingest.superbet.client import SuperbetClient
    except ImportError:
        return None

    client = SuperbetClient()
    if superbet_event_id:
        try:
            snap = client.fetch_event(superbet_event_id)
            if snap.inplay and snap.inplay.minute is not None:
                return int(snap.inplay.minute)
        except Exception:
            pass

    try:
        live = client.fetch_live_events()
    except Exception:
        return None

    for ev in live:
        if superbet_event_id and ev.event_id == superbet_event_id:
            if ev.minute is not None:
                return int(ev.minute)
        if _teams_match(home_team, away_team, ev.home_team, ev.away_team):
            if ev.minute is not None:
                return int(ev.minute)
    return None


def resolve_live_minute(
    *,
    minute: int | None,
    superbet_event_id: int | None,
    home_team: str,
    away_team: str,
) -> int | None:
    """Resolve minuto do jogo para guardrails (payload → API → lake local)."""
    if minute is not None:
        return minute

    resolved = _minute_from_superbet_api(
        superbet_event_id=superbet_event_id,
        home_team=home_team,
        away_team=away_team,
    )
    if resolved is not None:
        return resolved

    if superbet_event_id:
        local = _minute_from_local_event(superbet_event_id)
        if local is not None:
            return local

    return _minute_from_local_teams(home_team, away_team)


def is_extension_source(source: str | None) -> bool:
    return (source or "").strip().lower() in _EXTENSION_SOURCES


def _is_multi_or_combo(picks: list[dict[str, Any]]) -> bool:
    if len(picks) > 1:
        return True
    return any(str(p.get("market", "")).lower() == "combo" for p in picks)


def _all_picks_second_half(picks: list[dict[str, Any]]) -> bool:
    if not picks:
        return False
    for p in picks:
        eff = effective_guardrail_market(
            str(p.get("market", "")),
            outcome=str(p.get("outcome", "")),
            target_value=p.get("target_value"),
        )
        if not is_second_half_market(eff):
            return False
    return True


def bet_market_fingerprint(
    *,
    superbet_event_id: int | None,
    home_team: str,
    away_team: str,
    market: str,
    outcome: str,
) -> tuple[Any, ...]:
    """Chave única por evento + mercado + palpite normalizado."""
    norm_out = _normalize_outcome(market, outcome, home_team=home_team, away_team=away_team)
    event_key = superbet_event_id if superbet_event_id else f"{home_team}|{away_team}"
    return (event_key, market.lower(), norm_out)


def find_duplicate_open_bet(
    existing_bets: list[dict[str, Any]],
    *,
    superbet_event_id: int | None,
    home_team: str,
    away_team: str,
    picks: list[dict[str, Any]],
    exclude_bet_id: str | None = None,
) -> dict[str, Any] | None:
    """Retorna aposta aberta conflitante (mesmo mercado no mesmo jogo)."""
    if not picks:
        return None
    pick = picks[0]
    target = bet_market_fingerprint(
        superbet_event_id=superbet_event_id,
        home_team=home_team,
        away_team=away_team,
        market=str(pick.get("market", "")),
        outcome=str(pick.get("outcome", "")),
    )
    for bet in existing_bets:
        if exclude_bet_id and bet.get("id") == exclude_bet_id:
            continue
        if bet.get("status", "open") != "open":
            continue
        bpicks = bet.get("picks") or []
        if not bpicks:
            continue
        bp = bpicks[0]
        key = bet_market_fingerprint(
            superbet_event_id=bet.get("superbet_event_id"),
            home_team=str(bet.get("home_team", "")),
            away_team=str(bet.get("away_team", "")),
            market=str(bp.get("market", "")),
            outcome=str(bp.get("outcome", "")),
        )
        if key == target:
            return bet
    return None


def _scores_from_local_event(event_id: int) -> tuple[int, int, int | None, int | None]:
    """Placar e HT do último snapshot bronze."""
    path = Path(settings.lake_root) / "bronze" / "superbet" / "events" / str(event_id) / "latest.json"
    if not path.exists():
        return 0, 0, None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0, None, None
    inplay = payload.get("inplay") or {}
    home = int(inplay.get("home_score") or 0)
    away = int(inplay.get("away_score") or 0)
    ht_h = inplay.get("ht_home_score")
    ht_a = inplay.get("ht_away_score")
    return home, away, (int(ht_h) if ht_h is not None else None), (int(ht_a) if ht_a is not None else None)


def validate_register_open_bet(
    *,
    existing_bets: list[dict[str, Any]],
    superbet_event_id: int | None,
    home_team: str,
    away_team: str,
    picks: list[dict[str, Any]],
    bet_id: str | None = None,
    minute: int | None = None,
    stake: float | None = None,
    source: str | None = None,
    allow_duplicate: bool = False,
) -> None:
    """Levanta ``BetGuardrailError`` se a aposta violar regras P0."""
    if not settings.bet_guardrails_enabled:
        return

    if stake is not None and stake > settings.bet_max_stake:
        raise BetGuardrailError(
            "stake_cap",
            f"Stake R$ {stake:.2f} excede o teto de R$ {settings.bet_max_stake:.2f} por bilhete.",
        )

    if settings.bet_require_minute_extension and is_extension_source(source) and minute is None:
        raise BetGuardrailError(
            "minute_required",
            "Não foi possível determinar o minuto do jogo. "
            "Apostas da extensão são bloqueadas sem minuto (hit rate ~0% após 90'). "
            "Abra o bilhete com o placar visível ou aguarde o painel Ao Vivo.",
        )

    if minute is not None and minute >= settings.live_hard_stop_minute:
        raise BetGuardrailError(
            "hard_stop",
            f"Apostas bloqueadas após {settings.live_hard_stop_minute}' "
            f"(minuto atual: {minute}'). Histórico: hit 0% em 90+'. "
            "Use apenas cash-out em bilhetes já abertos.",
        )

    if minute is not None and picks:
        if settings.bet_block_multis_late and _is_multi_or_combo(picks):
            if minute >= settings.live_block_minute and not _all_picks_second_half(picks):
                raise BetGuardrailError(
                    "block_multis_late",
                    f"Múltiplas e combos bloqueados após {settings.live_block_minute}' "
                    f"(minuto atual: {minute}').",
                )

        blocked = []
        for p in picks:
            eff = effective_guardrail_market(
                str(p.get("market", "")),
                outcome=str(p.get("outcome", "")),
                target_value=p.get("target_value"),
            )
            if is_market_blocked_by_minute(eff, minute):
                blocked.append(str(p.get("market", "")))
        if blocked:
            market = blocked[0]
            eff = effective_guardrail_market(
                market,
                outcome=str(picks[0].get("outcome", "")),
                target_value=picks[0].get("target_value"),
            )
            block_at = market_live_block_minute(eff)
            raise BetGuardrailError(
                "block_midgame",
                f"Apostas em '{market}' bloqueadas após {block_at}' "
                f"(minuto atual: {minute}'). Use apenas cash-out em bilhetes abertos.",
            )

        if settings.live_ht_over_trap_block_dead and minute is not None:
            from models.inplay_bet_builder_guard import assess_ht_over_trap, infer_market_from_label

            home_score, away_score, ht_h, ht_a = (0, 0, None, None)
            if superbet_event_id:
                home_score, away_score, ht_h, ht_a = _scores_from_local_event(superbet_event_id)

            for p in picks:
                market = str(p.get("market") or "")
                outcome = str(p.get("outcome") or "yes")
                if market in {"other", "combo", "totals"} or not market:
                    inferred = infer_market_from_label(
                        str(p.get("target_value") or p.get("label") or "")
                    )
                    if inferred:
                        market, outcome = inferred
                trap = assess_ht_over_trap(
                    market,
                    outcome,
                    minute=minute,
                    home_score=home_score,
                    away_score=away_score,
                    ht_home=ht_h,
                    ht_away=ht_a,
                    label=p.get("target_value") or p.get("label"),
                )
                if trap and trap.get("severity") == "critical":
                    raise BetGuardrailError("ht_over_dead", trap["reason"])

        if len(picks) >= 2 and minute is not None:
            from models.inplay_bet_builder_guard import validate_bet_builder

            home_score, away_score, ht_h, ht_a = (0, 0, None, None)
            if superbet_event_id:
                home_score, away_score, ht_h, ht_a = _scores_from_local_event(superbet_event_id)

            validation = validate_bet_builder(
                picks,
                minute=minute,
                home_score=home_score,
                away_score=away_score,
                ht_home=ht_h,
                ht_away=ht_a,
                combined_odd=None,
            )
            for err in validation.get("errors") or []:
                if err.get("code") == "ht_over_dead":
                    raise BetGuardrailError("ht_over_dead", str(err.get("reason", "")))
                if err.get("code") in {"legs_incompatible", "combo_invalid"}:
                    raise BetGuardrailError(
                        "combo_invalid",
                        str(err.get("reason", "Combo inválido na Superbet.")),
                    )

    if not allow_duplicate and settings.bet_one_per_market_enabled:
        dup = find_duplicate_open_bet(
            existing_bets,
            superbet_event_id=superbet_event_id,
            home_team=home_team,
            away_team=away_team,
            picks=picks,
            exclude_bet_id=bet_id,
        )
        if dup:
            pick = picks[0]
            raise BetGuardrailError(
                "duplicate_market",
                (
                    f"Já existe aposta aberta neste mercado "
                    f"({pick.get('market')} / {pick.get('outcome')}) "
                    f"para {home_team} × {away_team}. "
                    "Regra P0: máximo 1 bilhete por mercado por jogo."
                ),
            )


@dataclass
class BetGuardrailsPayload:
    """Metadados expostos na API ao vivo para a UI."""

    enabled: bool
    block_new_bets: bool
    block_new_bets_2h: bool
    allow_2h_suggestions: bool
    block_minute: int
    block_2h_minute: int
    hard_stop_minute: int
    block_reason: str | None
    one_bet_per_market: bool
    max_stake: float
    pregame_palpite: str | None = None
    pregame_prob: float | None = None
    inplay_palpite: str | None = None
    inplay_prob: float | None = None
    ht_trap_warnings: list[dict[str, Any]] | None = None
    bet_builder_rules: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "block_new_bets": self.block_new_bets,
            "block_new_bets_2h": self.block_new_bets_2h,
            "allow_2h_suggestions": self.allow_2h_suggestions,
            "block_minute": self.block_minute,
            "block_2h_minute": self.block_2h_minute,
            "hard_stop_minute": self.hard_stop_minute,
            "block_reason": self.block_reason,
            "one_bet_per_market": self.one_bet_per_market,
            "max_stake": self.max_stake,
            "pregame_palpite": self.pregame_palpite,
            "pregame_prob": self.pregame_prob,
            "inplay_palpite": self.inplay_palpite,
            "inplay_prob": self.inplay_prob,
            "ht_trap_warnings": self.ht_trap_warnings or [],
            "bet_builder_rules": self.bet_builder_rules or [],
        }


def build_bet_guardrails_payload(
    *,
    minute: int,
    pregame_prediction: str | None = None,
    pregame_probs: dict[str, float] | None = None,
    inplay_probs: dict[str, float] | None = None,
    home_score: int = 0,
    away_score: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    market_scan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Payload para frontend Ao Vivo."""
    from models.inplay_bet_builder_guard import scan_ht_over_traps, _bet_builder_rules_text
    from models.inplay_market_period import allow_2h_suggestions
    from models.wc_draw_model import resolve_wc_outcome

    hard_stop = minute >= settings.live_hard_stop_minute
    block_ft = settings.bet_guardrails_enabled and minute >= settings.live_block_minute
    block_2h = settings.bet_guardrails_enabled and minute >= settings.live_block_2h_minute
    block_reason = None
    if hard_stop:
        block_reason = (
            f"Fim de jogo (≥{settings.live_hard_stop_minute}') — "
            "sem novas apostas (hit 0% em 90+' no histórico). "
            "Apenas cash-out."
        )
    elif block_ft and not allow_2h_suggestions(minute):
        block_reason = (
            f"Hit rate cai de ~60% para ~27% em mercados do jogo inteiro após "
            f"{settings.live_block_minute}'. Novos aportes FT desativados — "
            f"mercados do 2T ainda disponíveis até {settings.live_block_2h_minute}'."
        )
    elif block_ft and allow_2h_suggestions(minute):
        block_reason = (
            f"Mercados do jogo inteiro bloqueados após {settings.live_block_minute}'. "
            f"Sugestões limitadas ao 2º tempo (até {settings.live_block_2h_minute}')."
        )
    elif block_2h:
        block_reason = (
            f"Pouco tempo restante (≥{settings.live_block_2h_minute}') — "
            "sem novas sugestões de mercado."
        )

    inplay_pal = None
    inplay_p = None
    if inplay_probs:
        inplay_pal = resolve_wc_outcome(inplay_probs, phase="friendly")
        inplay_p = inplay_probs.get(inplay_pal)

    pre_p = None
    if pregame_prediction and pregame_probs:
        pre_p = pregame_probs.get(pregame_prediction)

    ht_traps = scan_ht_over_traps(
        market_scan or [],
        minute=minute,
        home_score=home_score,
        away_score=away_score,
        ht_home=ht_home,
        ht_away=ht_away,
    )

    return BetGuardrailsPayload(
        enabled=settings.bet_guardrails_enabled,
        block_new_bets=block_ft or hard_stop,
        block_new_bets_2h=block_2h or hard_stop,
        allow_2h_suggestions=allow_2h_suggestions(minute) and not hard_stop,
        block_minute=settings.live_block_minute,
        block_2h_minute=settings.live_block_2h_minute,
        hard_stop_minute=settings.live_hard_stop_minute,
        block_reason=block_reason,
        one_bet_per_market=settings.bet_one_per_market_enabled,
        max_stake=settings.bet_max_stake,
        pregame_palpite=pregame_prediction,
        pregame_prob=round(pre_p, 4) if pre_p is not None else None,
        inplay_palpite=inplay_pal,
        inplay_prob=round(inplay_p, 4) if inplay_p is not None else None,
        ht_trap_warnings=ht_traps,
        bet_builder_rules=_bet_builder_rules_text(),
    ).to_dict()


__all__ = [
    "BetGuardrailError",
    "BetGuardrailsPayload",
    "bet_market_fingerprint",
    "build_bet_guardrails_payload",
    "find_duplicate_open_bet",
    "is_extension_source",
    "resolve_live_minute",
    "validate_register_open_bet",
]
