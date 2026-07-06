"""Avaliação de risco de cash-out para apostas abertas (simples e combo).

Detecta pernas em zona crítica (ex.: under 2.5 com 2 gols) e orienta sair
com cash-out parcial quando a casa oferece valor e o bilhete pode morrer em 1 evento.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from models.open_bet_settle import evaluate_pick

LegLiveStatus = Literal["won", "lost", "critical", "at_risk", "pending", "ok"]
RiskAction = Literal["exit_now", "protect_stake", "consider_exit", "hold", "dead"]

_LINE_RE = re.compile(
    r"(?P<dir>mais|menos|over|under|acima|abaixo)\s*(?:de\s*)?(?P<line>\d+[.,]?\d*)",
    re.IGNORECASE,
)
_MARKET_LINE_RE = re.compile(r"(?:^|_)(?:over|under|totals)_(\d+)_(\d+)", re.IGNORECASE)
_PERIOD_RE = re.compile(r"^(1h|2h|1t|2t)_", re.IGNORECASE)


@dataclass
class LegRiskAssessment:
    market: str
    outcome: str
    label: str
    status: LegLiveStatus
    reason: str = ""


@dataclass
class CashoutRiskAssessment:
    bet_id: str
    action: RiskAction
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    message: str
    stake: float
    cashout_value: float | None
    potential_return: float
    cashout_pct_of_stake: float | None
    cashout_pct_of_potential: float | None
    legs: list[LegRiskAssessment] = field(default_factory=list)
    critical_legs: list[str] = field(default_factory=list)
    alert: bool = False


def _parse_score(score: str | None) -> tuple[int, int]:
    if not score:
        return 0, 0
    parts = re.split(r"[x×:\-]", str(score).strip(), maxsplit=1)
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return 0, 0


def _parse_line_from_text(text: str) -> tuple[str | None, float | None]:
    lower = text.lower()
    m = _LINE_RE.search(lower)
    if not m:
        return None, None
    direction_raw = m.group("dir").lower()
    line = float(m.group("line").replace(",", "."))
    direction = "over" if direction_raw in {"mais", "over", "acima"} else "under"
    return direction, line


def _normalize_totals_pick(
    market: str,
    outcome: str,
    target_value: str | None,
    label: str,
) -> tuple[str, str, float | None, bool]:
    """Retorna (market_norm, direction, line, is_first_half)."""
    mkt = (market or "").lower()
    out = (outcome or "").lower()
    lbl = label or ""
    blob = f"{mkt} {out} {target_value or ''} {lbl}"
    is_1h = bool(_PERIOD_RE.match(mkt)) or "1º tempo" in lbl.lower() or "1o tempo" in lbl.lower()

    mm = _MARKET_LINE_RE.search(mkt.replace("-", "_"))
    if mm:
        line = float(f"{mm.group(1)}.{mm.group(2)}")
        if out in {"yes", "over", "sim"}:
            return f"totals_{line}", "over", line, is_1h
        if out in {"no", "under", "não", "nao"}:
            return f"totals_{line}", "under", line, is_1h

    direction, line = _parse_line_from_text(blob)
    if direction and line is not None:
        return f"totals_{line}", direction, line, is_1h

    if mkt.startswith("totals"):
        line = target_value
        try:
            ln = float(str(line).replace(",", ".")) if line else 2.5
        except ValueError:
            ln = 2.5
        if out in {"over", "yes"}:
            return mkt, "over", ln, is_1h
        if out in {"under", "no"}:
            return mkt, "under", ln, is_1h

    return mkt, out, None, is_1h


def _max_goals_for_under(line: float) -> int:
    """Under 2.5 → no máximo 2 gols; under 3.5 → no máximo 3."""
    return math.floor(line)


def _min_goals_for_over(line: float) -> int:
    """Over 1.5 → precisa 2+ gols."""
    return math.floor(line) + 1


def _evaluate_under_over_live(
    *,
    current: float,
    line: float,
    direction: str,
    unit: str,
    scope: str,
    minute: int,
    late_minute: int = 60,
) -> tuple[LegLiveStatus, str]:
    """Estado ao vivo para mercados over/under (gols, escanteios, cartões)."""
    if direction == "under":
        limit = _max_goals_for_under(line)
        if current >= limit + 1:
            return "lost", f"Acima de {line} {unit} {scope}."
        if current == limit:
            return (
                "critical",
                f"«{line} {unit}»: {int(current)} — um a mais mata a perna ({scope}).",
            )
        if current == limit - 1 and minute >= late_minute:
            return (
                "at_risk",
                f"Perto do limite ({int(current)} {unit}, max {limit} {scope}).",
            )
    elif direction == "over":
        need = _min_goals_for_over(line)
        if current >= need:
            return "won", f"Over {line} {unit} batido."
        if need - current == 1 and minute >= 70:
            return "at_risk", f"Falta 1 {unit[:-1] if unit.endswith('s') else unit} ({minute}')."
    return "pending", ""


def _parse_line_value(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None


def evaluate_leg_live(
    pick: dict[str, Any],
    *,
    home_score: int,
    away_score: int,
    minute: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    period_label: str | None = None,
    home_corners: int | None = None,
    away_corners: int | None = None,
    home_cards: int | None = None,
    away_cards: int | None = None,
) -> LegRiskAssessment:
    market = str(pick.get("market") or "")
    outcome = str(pick.get("outcome") or "")
    label = str(pick.get("label") or pick.get("outcome") or market)
    target_value = pick.get("target_value")

    settled = evaluate_pick(
        market=market,
        outcome=outcome,
        target_value=target_value,
        home_score=home_score,
        away_score=away_score,
        home_corners=home_corners,
        away_corners=away_corners,
    )
    if settled is False:
        return LegRiskAssessment(market, outcome, label, "lost", "Perna perdida.")
    # Under e 1X2 podem virar ao vivo — só marca vitória irreversível (ex.: over batido)
    out_l = outcome.lower()
    mkt_l_early = market.lower()
    if settled is True:
        if out_l in {"under", "no", "não", "nao"}:
            pass
        elif mkt_l_early in {"h2h", "1", "2", "x"} or out_l in {"1", "2", "x", "home", "away", "draw"}:
            pass
        else:
            return LegRiskAssessment(market, outcome, label, "won", "Perna já ganha.")

    mkt_l = market.lower()
    lbl_l = label.lower()

    # Escanteios (under 4.5 etc.)
    if mkt_l == "corners_total" or "escanteio" in lbl_l:
        line = _parse_line_value(target_value)
        if line is None:
            _, line = _parse_line_from_text(lbl_l)
        if line is not None and home_corners is not None and away_corners is not None:
            total = home_corners + away_corners
            direction = outcome.lower() if outcome.lower() in {"over", "under"} else (
                "over" if outcome.lower() in {"yes", "sim"} else "under"
            )
            status, reason = _evaluate_under_over_live(
                current=total,
                line=line,
                direction=direction,
                unit="escanteios",
                scope="no jogo",
                minute=minute,
            )
            if status != "pending":
                return LegRiskAssessment(market, outcome, label, status, reason)

    # Cartões (label ou mercado genérico)
    if mkt_l in {"cards_total", "other"} and ("cartão" in lbl_l or "cartao" in lbl_l):
        line = _parse_line_value(target_value)
        if line is None:
            _, line = _parse_line_from_text(lbl_l)
        if line is not None and home_cards is not None and away_cards is not None:
            total = home_cards + away_cards
            direction = "under"
            if outcome.lower() in {"over", "yes", "sim"}:
                direction = "over"
            elif outcome.lower() in {"under", "no", "não", "nao"}:
                direction = "under"
            elif "mais" in lbl_l or "over" in lbl_l:
                direction = "over"
            status, reason = _evaluate_under_over_live(
                current=total,
                line=line,
                direction=direction,
                unit="cartões",
                scope="no jogo",
                minute=minute,
            )
            if status != "pending":
                return LegRiskAssessment(market, outcome, label, status, reason)

    mkt_norm, direction, line, is_1h = _normalize_totals_pick(
        market, outcome, target_value, label
    )
    period = (period_label or "").lower()
    in_first_half = minute <= 45 or "1" in period[:2] if period else minute <= 45

    if direction and line is not None:
        if is_1h and ht_home is not None and ht_away is not None:
            goals = ht_home + ht_away
            scope = "no 1º tempo"
        elif is_1h and in_first_half:
            goals = home_score + away_score
            scope = "no 1º tempo"
        else:
            goals = home_score + away_score
            scope = "no jogo"

        if direction == "under":
            limit = _max_goals_for_under(line)
            if goals >= limit + 1:
                return LegRiskAssessment(
                    market, outcome, label, "lost", f"Acima de {line} gols {scope}."
                )
            if goals == limit:
                return LegRiskAssessment(
                    market,
                    outcome,
                    label,
                    "critical",
                    f"«{label}»: {goals} gols — um gol a mais mata a perna ({scope}).",
                )
            if goals == limit - 1 and minute >= 60:
                return LegRiskAssessment(
                    market,
                    outcome,
                    label,
                    "at_risk",
                    f"«{label}»: perto do limite ({goals} gols, max {limit} {scope}).",
                )
        elif direction == "over":
            need = _min_goals_for_over(line)
            if goals >= need:
                return LegRiskAssessment(market, outcome, label, "won", f"Over {line} batido.")
            remaining = need - goals
            if remaining == 1 and minute >= 70:
                return LegRiskAssessment(
                    market,
                    outcome,
                    label,
                    "at_risk",
                    f"«{label}»: falta 1 gol com pouco tempo ({minute}').",
                )

    # h2h ao vivo
    m_l = market.lower()
    o_l = outcome.lower()
    if m_l in {"h2h", "1", "2", "x"} or o_l in {"1", "2", "x", "home", "away", "draw"}:
        side = o_l if o_l in {"1", "2", "x"} else ("1" if o_l == "home" else "2" if o_l == "away" else "x")
        if m_l in {"1", "2", "x"}:
            side = m_l
        gap = home_score - away_score
        if side == "1" and gap <= -2:
            return LegRiskAssessment(
                market, outcome, label, "at_risk", "Mandante perdendo por 2+ — vitória difícil."
            )
        if side == "2" and gap >= 2:
            return LegRiskAssessment(
                market, outcome, label, "ok", "Visitante confortável no placar."
            )

    return LegRiskAssessment(market, outcome, label, "pending", "")


def assess_cashout_risk(
    bet: dict[str, Any],
    *,
    home_score: int,
    away_score: int,
    minute: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    period_label: str | None = None,
    home_corners: int | None = None,
    away_corners: int | None = None,
    home_cards: int | None = None,
    away_cards: int | None = None,
    min_protect_pct: float = 0.5,
) -> CashoutRiskAssessment:
    """Avalia se cash-out agora é melhor que segurar até o fim."""
    bet_id = str(bet.get("id") or "")
    stake = float(bet.get("stake") or 0)
    potential = float(bet.get("potential_return") or stake * float(bet.get("odds_placed") or 1))
    cashout = bet.get("cashout_value")
    cashout_f = float(cashout) if cashout is not None else None

    odds = float(bet.get("odds_placed") or 1)
    picks = bet.get("picks") or [{}]
    legs = [
        evaluate_leg_live(
            p if isinstance(p, dict) else {},
            home_score=home_score,
            away_score=away_score,
            minute=minute,
            ht_home=ht_home,
            ht_away=ht_away,
            period_label=period_label,
            home_corners=home_corners,
            away_corners=away_corners,
            home_cards=home_cards,
            away_cards=away_cards,
        )
        for p in picks
    ]

    critical = [lg.label for lg in legs if lg.status == "critical"]
    lost = [lg.label for lg in legs if lg.status == "lost"]
    at_risk = [lg.label for lg in legs if lg.status == "at_risk"]

    pct_stake = round(cashout_f / stake, 3) if cashout_f is not None and stake > 0 else None
    pct_pot = round(cashout_f / potential, 3) if cashout_f is not None and potential > 0 else None

    if lost:
        return CashoutRiskAssessment(
            bet_id=bet_id,
            action="dead",
            severity="critical",
            title="Bilhete perdido",
            message="Uma ou mais pernas já falharam. Cash-out tende a zero.",
            stake=stake,
            cashout_value=cashout_f,
            potential_return=potential,
            cashout_pct_of_stake=pct_stake,
            cashout_pct_of_potential=pct_pot,
            legs=legs,
            critical_legs=critical,
            alert=False,
        )

    if critical and cashout_f is not None and cashout_f >= stake:
        return CashoutRiskAssessment(
            bet_id=bet_id,
            action="exit_now",
            severity="critical",
            title="Cash-out recomendado — perna em risco",
            message=(
                f"A casa oferece R$ {cashout_f:.2f} (lucro sobre a stake). "
                f"Perna(s) crítica(s): {', '.join(critical[:2])}. "
                "Um gol/evento pode zerar o bilhete — considere sair agora."
            ),
            stake=stake,
            cashout_value=cashout_f,
            potential_return=potential,
            cashout_pct_of_stake=pct_stake,
            cashout_pct_of_potential=pct_pot,
            legs=legs,
            critical_legs=critical,
            alert=True,
        )

    if critical and cashout_f is not None and stake > 0 and pct_stake is not None:
        if pct_stake >= min_protect_pct:
            return CashoutRiskAssessment(
                bet_id=bet_id,
                action="protect_stake",
                severity="high",
                title="Proteja parte do valor",
                message=(
                    f"Cash-out R$ {cashout_f:.2f} ({pct_stake:.0%} da aposta). "
                    f"Risco alto em: {', '.join(critical[:2])}. "
                    "Melhor recuperar parte do que perder tudo."
                ),
                stake=stake,
                cashout_value=cashout_f,
                potential_return=potential,
                cashout_pct_of_stake=pct_stake,
                cashout_pct_of_potential=pct_pot,
                legs=legs,
                critical_legs=critical,
                alert=True,
            )

    if critical and cashout_f is not None and cashout_f > 0:
        return CashoutRiskAssessment(
            bet_id=bet_id,
            action="consider_exit",
            severity="high",
            title="Risco alto no bilhete",
            message=(
                f"Perna(s) a um passo de perder: {', '.join(critical[:2])}. "
                f"Cash-out disponível: R$ {cashout_f:.2f}."
            ),
            stake=stake,
            cashout_value=cashout_f,
            potential_return=potential,
            cashout_pct_of_stake=pct_stake,
            cashout_pct_of_potential=pct_pot,
            legs=legs,
            critical_legs=critical,
            alert=True,
        )

    if at_risk and cashout_f is not None and cashout_f >= stake * 1.05:
        return CashoutRiskAssessment(
            bet_id=bet_id,
            action="consider_exit",
            severity="medium",
            title="Considere cash-out",
            message=(
                f"Cash-out com lucro (R$ {cashout_f:.2f}) enquanto há pressão em: "
                f"{', '.join(at_risk[:2])}."
            ),
            stake=stake,
            cashout_value=cashout_f,
            potential_return=potential,
            cashout_pct_of_stake=pct_stake,
            cashout_pct_of_potential=pct_pot,
            legs=legs,
            critical_legs=critical,
            alert=True,
        )

    # Bilhete longo (odd alta) com cash-out derretendo — sair antes de zerar
    if (
        cashout_f is not None
        and cashout_f > 0
        and pct_stake is not None
        and pct_stake < 0.45
        and odds >= 8
        and not critical
    ):
        return CashoutRiskAssessment(
            bet_id=bet_id,
            action="consider_exit",
            severity="high",
            title="Cash-out caindo — zera fácil",
            message=(
                f"Cash-out só R$ {cashout_f:.2f} ({pct_stake:.0%} da aposta) num bilhete @ {odds:.1f}. "
                "Recupere o que ainda dá antes de perder tudo."
            ),
            stake=stake,
            cashout_value=cashout_f,
            potential_return=potential,
            cashout_pct_of_stake=pct_stake,
            cashout_pct_of_potential=pct_pot,
            legs=legs,
            critical_legs=critical,
            alert=True,
        )

    # Lucro disponível no cash-out — garantir ganho
    if (
        cashout_f is not None
        and stake > 0
        and cashout_f >= stake * 1.08
        and not critical
        and not at_risk
    ):
        return CashoutRiskAssessment(
            bet_id=bet_id,
            action="consider_exit",
            severity="medium",
            title="Garanta o lucro",
            message=(
                f"Cash-out R$ {cashout_f:.2f} — acima da aposta (R$ {stake:.2f}). "
                "Considere sair e travar o ganho."
            ),
            stake=stake,
            cashout_value=cashout_f,
            potential_return=potential,
            cashout_pct_of_stake=pct_stake,
            cashout_pct_of_potential=pct_pot,
            legs=legs,
            critical_legs=critical,
            alert=True,
        )

    return CashoutRiskAssessment(
        bet_id=bet_id,
        action="hold",
        severity="low",
        title="Sem alerta de saída",
        message="Nenhuma perna crítica detectada ou cash-out indisponível.",
        stake=stake,
        cashout_value=cashout_f,
        potential_return=potential,
        cashout_pct_of_stake=pct_stake,
        cashout_pct_of_potential=pct_pot,
        legs=legs,
        critical_legs=critical,
        alert=False,
    )


__all__ = [
    "LegRiskAssessment",
    "CashoutRiskAssessment",
    "evaluate_leg_live",
    "assess_cashout_risk",
    "_parse_score",
]
