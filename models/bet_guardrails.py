"""Regras P0 de proteção operacional para apostas ao vivo."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from models.wc_against_model import normalize_h2h_outcome


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


def validate_register_open_bet(
    *,
    existing_bets: list[dict[str, Any]],
    superbet_event_id: int | None,
    home_team: str,
    away_team: str,
    picks: list[dict[str, Any]],
    bet_id: str | None = None,
    minute: int | None = None,
    allow_duplicate: bool = False,
) -> None:
    """Levanta ``BetGuardrailError`` se a aposta violar regras P0."""
    if not settings.bet_guardrails_enabled:
        return

    if minute is not None and minute >= settings.live_block_minute:
        raise BetGuardrailError(
            "block_midgame",
            f"Apostas novas bloqueadas após {settings.live_block_minute}' "
            f"(minuto atual: {minute}'). Use apenas cash-out em bilhetes abertos.",
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
    block_minute: int
    block_reason: str | None
    one_bet_per_market: bool
    pregame_palpite: str | None = None
    pregame_prob: float | None = None
    inplay_palpite: str | None = None
    inplay_prob: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "block_new_bets": self.block_new_bets,
            "block_minute": self.block_minute,
            "block_reason": self.block_reason,
            "one_bet_per_market": self.one_bet_per_market,
            "pregame_palpite": self.pregame_palpite,
            "pregame_prob": self.pregame_prob,
            "inplay_palpite": self.inplay_palpite,
            "inplay_prob": self.inplay_prob,
        }


def build_bet_guardrails_payload(
    *,
    minute: int,
    pregame_prediction: str | None = None,
    pregame_probs: dict[str, float] | None = None,
    inplay_probs: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Payload para frontend Ao Vivo."""
    from models.wc_draw_model import resolve_wc_outcome

    block = settings.bet_guardrails_enabled and minute >= settings.live_block_minute
    block_reason = None
    if block:
        block_reason = (
            f"Hit rate cai de ~60% para ~27% após {settings.live_block_minute}'. "
            "Novos aportes desativados — proteja bilhetes abertos (cash-out)."
        )

    inplay_pal = None
    inplay_p = None
    if inplay_probs:
        inplay_pal = resolve_wc_outcome(inplay_probs, phase="friendly")
        inplay_p = inplay_probs.get(inplay_pal)

    pre_p = None
    if pregame_prediction and pregame_probs:
        pre_p = pregame_probs.get(pregame_prediction)

    return BetGuardrailsPayload(
        enabled=settings.bet_guardrails_enabled,
        block_new_bets=block,
        block_minute=settings.live_block_minute,
        block_reason=block_reason,
        one_bet_per_market=settings.bet_one_per_market_enabled,
        pregame_palpite=pregame_prediction,
        pregame_prob=round(pre_p, 4) if pre_p is not None else None,
        inplay_palpite=inplay_pal,
        inplay_prob=round(inplay_p, 4) if inplay_p is not None else None,
    ).to_dict()


__all__ = [
    "BetGuardrailError",
    "BetGuardrailsPayload",
    "bet_market_fingerprint",
    "build_bet_guardrails_payload",
    "find_duplicate_open_bet",
    "validate_register_open_bet",
]
