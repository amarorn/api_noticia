"""Hedge Advisor — monitora apostas abertas e sugere proteção em tempo real.

Fluxo:
  1. Recebe apostas abertas do usuário (de user_open_bets.json)
  2. Para cada aposta, calcula probabilidade ATUAL do outcome (via modelo in-play)
  3. Compara EV remanescente com thresholds
  4. Sugere: CASH-OUT, HEDGE (contra-aposta), SHIFT (mercado melhor) ou MANTER
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ingest.superbet.parser import SuperbetEventSnapshot

logger = logging.getLogger(__name__)

# ── Thresholds de decisão ──
_EV_CASHOUT_URGENT = -0.60  # EV remanescente < -60% → cash-out urgente
_EV_HEDGE_TRIGGER = -0.10   # EV remanescente < -10% → sugerir hedge
_EV_SHIFT_TRIGGER = 0.05    # EV positivo mas < 5% → avaliar shift
_MIN_HEDGE_GAIN = 5.0       # R$ mínimo de ganho para sugerir hedge


@dataclass
class HedgeSuggestion:
    """Sugestão de contra-aposta para proteger uma posição."""

    market: str
    outcome: str
    odd_current: float
    stake_suggested: float
    guaranteed_return: float  # retorno se o hedge acertar
    net_if_original_wins: float  # lucro líquido se a original ganhar
    net_if_hedge_wins: float  # lucro/perda se o hedge ganhar


@dataclass
class BetAdvice:
    """Conselho para uma aposta individual do usuário."""

    bet_id: str
    event_name: str
    market: str
    outcome: str
    stake: float
    odds_placed: float
    potential_return: float

    # Análise do modelo
    prob_current: float  # probabilidade ATUAL do outcome
    ev_remaining: float  # EV remanescente = P × odds - 1
    prob_at_entry: float | None = None  # prob quando apostou (se conhecido)

    # Decisão
    action: str = "hold"  # "cashout" | "hedge" | "hold" | "shift"
    urgency: str = "low"  # "critical" | "high" | "medium" | "low"

    # Sugestões
    hedge: HedgeSuggestion | None = None
    cashout_value: float | None = None
    shift_market: str | None = None
    shift_detail: str | None = None

    # Explicação
    reasoning: str = ""


@dataclass
class HedgeReport:
    """Relatório completo de proteção para todas as apostas do usuário."""

    advices: list[BetAdvice] = field(default_factory=list)
    total_at_risk: float = 0.0
    total_potential: float = 0.0
    overall_action: str = "hold"  # ação dominante
    summary: str = ""


def _get_prob_for_outcome(
    inplay: dict[str, Any],
    market: str,
    outcome: str,
) -> float | None:
    """Extrai a probabilidade atual do modelo para um outcome específico."""
    # H2H (1X2)
    if market == "h2h":
        if outcome in ("home", "1"):
            return inplay.get("prob_final_home")
        if outcome in ("away", "2"):
            return inplay.get("prob_final_away")
        if outcome in ("draw", "X"):
            return inplay.get("prob_final_draw")

    # Totais (over/under)
    if market.startswith("totals"):
        line_probs = inplay.get("final_line_probs") or {}
        # Extrair a linha: "totals_3.5" → "over_3_5" ou "under_3_5"
        parts = market.split("_", 1)
        if len(parts) > 1:
            line_key = parts[1].replace(".", "_")
            if outcome == "over":
                return line_probs.get(f"over_{line_key}")
            return line_probs.get(f"under_{line_key}")
        # Genérico: totals sem linha específica → over_2_5
        if outcome == "over":
            return line_probs.get("over_2_5")
        return line_probs.get("under_2_5")

    # BTTS
    if market == "btts":
        btts_prob = inplay.get("btts_final")
        if btts_prob is not None:
            return btts_prob if outcome == "yes" else (1.0 - btts_prob)

    # Próximo gol
    if market == "next_goal":
        if "home" in outcome.lower():
            return inplay.get("prob_next_goal_home")
        if "away" in outcome.lower():
            return inplay.get("prob_next_goal_away")
        if "no" in outcome.lower() or "sem" in outcome.lower():
            return inplay.get("prob_no_more_goals")

    return None


def _get_opposite_outcome(market: str, outcome: str) -> tuple[str, str] | None:
    """Retorna (outcome_oposto, label_legível) para um dado mercado/outcome."""
    if market == "h2h":
        if outcome in ("home", "1"):
            return ("away", "Vitória visitante")
        if outcome in ("away", "2"):
            return ("home", "Vitória mandante")
        if outcome in ("draw", "X"):
            return ("home", "Vitória mandante")  # hedge de empate → aposta no favorito
    if market.startswith("totals"):
        if outcome == "over":
            return ("under", "Under (menos gols)")
        return ("over", "Over (mais gols)")
    if market == "btts":
        if outcome == "yes":
            return ("no", "Ambas NÃO marcam")
        return ("yes", "Ambas marcam")
    return None


def _get_current_odd_for_outcome(
    snapshot: SuperbetEventSnapshot | None,
    market: str,
    outcome: str,
) -> float | None:
    """Busca a odd atual da Superbet para um outcome."""
    if snapshot is None:
        return None

    # H2H
    if market == "h2h" and snapshot.h2h_odds:
        if outcome in ("home", "1"):
            return snapshot.h2h_odds.get("1")
        if outcome in ("away", "2"):
            return snapshot.h2h_odds.get("2")
        if outcome in ("draw", "X"):
            return snapshot.h2h_odds.get("X")

    # Totais
    if market.startswith("totals") and snapshot.totals:
        for total in snapshot.totals:
            line_str = market.split("_", 1)[-1] if "_" in market else "2.5"
            if str(total.get("line")) == line_str:
                if outcome == "over":
                    return total.get("over_odd")
                return total.get("under_odd")

    # BTTS
    if market == "btts" and snapshot.btts:
        if outcome == "yes":
            return snapshot.btts.get("yes_odd")
        return snapshot.btts.get("no_odd")

    return None


def _calculate_hedge(
    stake_original: float,
    odds_original: float,
    odds_hedge: float,
) -> HedgeSuggestion | None:
    """Calcula stake de hedge para break-even."""
    if odds_hedge <= 1.0:
        return None

    potential_original = stake_original * odds_original
    # Stake de hedge para igualar retorno:
    # Se hedge ganha: stake_hedge × odds_hedge - stake_original - stake_hedge = 0
    # stake_hedge = stake_original / (odds_hedge - 1)
    # Mas queremos garantir retorno = stake_original (break-even total)
    # Se original ganha: potential_original - stake_hedge
    # Se hedge ganha: stake_hedge × odds_hedge - stake_original
    # Igualar: potential_original - stake_hedge = stake_hedge × odds_hedge - stake_original
    # potential_original + stake_original = stake_hedge × (odds_hedge + 1)
    # NÃO — queremos break-even = 0 (não perder dinheiro):
    # Se hedge ganha: stake_hedge × odds_hedge >= stake_original + stake_hedge
    # stake_hedge × (odds_hedge - 1) >= stake_original
    # stake_hedge >= stake_original / (odds_hedge - 1)
    stake_hedge_breakeven = stake_original / (odds_hedge - 1)

    # Retorno garantido mínimo se usarmos break-even:
    net_if_original_wins = potential_original - stake_original - stake_hedge_breakeven
    net_if_hedge_wins = stake_hedge_breakeven * odds_hedge - stake_original - stake_hedge_breakeven

    if stake_hedge_breakeven <= 0 or net_if_original_wins < 0:
        return None

    return HedgeSuggestion(
        market="",  # preenchido pelo caller
        outcome="",
        odd_current=odds_hedge,
        stake_suggested=round(stake_hedge_breakeven, 2),
        guaranteed_return=round(min(net_if_original_wins, net_if_hedge_wins), 2),
        net_if_original_wins=round(net_if_original_wins, 2),
        net_if_hedge_wins=round(net_if_hedge_wins, 2),
    )


def advise_single_bet(
    bet: dict[str, Any],
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None = None,
    minute: int = 0,
) -> BetAdvice:
    """Analisa uma aposta individual e retorna conselho."""
    picks = bet.get("picks") or []
    if not picks:
        return BetAdvice(
            bet_id=bet.get("id", ""),
            event_name=bet.get("event_name", ""),
            market="unknown",
            outcome="unknown",
            stake=bet.get("stake", 0),
            odds_placed=bet.get("odds_placed", 0),
            potential_return=bet.get("potential_return", 0),
            prob_current=0,
            ev_remaining=-1.0,
            action="cashout",
            urgency="low",
            reasoning="Aposta sem picks — não monitorável.",
        )

    pick = picks[0]  # Para simples; múltipla seria mais complexa
    market = pick.get("market", "other")
    outcome = pick.get("outcome", "")
    stake = bet.get("stake", 0)
    odds_placed = bet.get("odds_placed", 0)
    potential_return = bet.get("potential_return", 0) or (stake * odds_placed)
    cashout_value = bet.get("cashout_value")

    # Probabilidade atual do modelo
    prob_current = _get_prob_for_outcome(inplay, market, outcome)
    if prob_current is None:
        # Mercado não mapeado → não podemos avaliar
        return BetAdvice(
            bet_id=bet.get("id", ""),
            event_name=bet.get("event_name", ""),
            market=market,
            outcome=outcome,
            stake=stake,
            odds_placed=odds_placed,
            potential_return=potential_return,
            prob_current=0,
            ev_remaining=0,
            action="hold",
            urgency="low",
            reasoning=f"Mercado '{market}' não mapeado no modelo in-play. Sem avaliação.",
        )

    # EV remanescente
    ev_remaining = prob_current * odds_placed - 1.0

    # Probabilidade implícita na odd de entrada (1/odd)
    prob_at_entry = 1.0 / odds_placed if odds_placed > 0 else 0

    # --- Decisão ---
    action = "hold"
    urgency = "low"
    reasoning = ""
    hedge_suggestion = None

    if ev_remaining < _EV_CASHOUT_URGENT:
        action = "cashout"
        urgency = "critical"
        expected_value = prob_current * potential_return
        reasoning = (
            f"EV remanescente {ev_remaining:.0%} — chance real {prob_current:.1%} "
            f"é muito baixa para a odd {odds_placed:.2f}. "
            f"Valor esperado: R$ {expected_value:.2f} vs stake R$ {stake:.2f}. "
        )
        if cashout_value:
            reasoning += f"Cash-out disponível: R$ {cashout_value:.2f}."
        else:
            reasoning += "Cash-out não disponível — considere hedge."

    elif ev_remaining < _EV_HEDGE_TRIGGER:
        action = "hedge"
        urgency = "high" if ev_remaining < -0.30 else "medium"
        reasoning = (
            f"EV caiu para {ev_remaining:.0%} — chance real {prob_current:.1%}. "
            f"Sugerimos proteger o capital com contra-aposta."
        )

        # Calcular hedge
        opposite = _get_opposite_outcome(market, outcome)
        if opposite and snapshot:
            opp_outcome, opp_label = opposite
            opp_odd = _get_current_odd_for_outcome(snapshot, market, opp_outcome)
            if opp_odd and opp_odd > 1.0:
                hedge_calc = _calculate_hedge(stake, odds_placed, opp_odd)
                if hedge_calc and hedge_calc.guaranteed_return >= _MIN_HEDGE_GAIN:
                    hedge_calc.market = market
                    hedge_calc.outcome = opp_outcome
                    hedge_suggestion = hedge_calc
                    reasoning += (
                        f" Contra-aposta: R$ {hedge_calc.stake_suggested:.2f} em "
                        f"'{opp_label}' @ {opp_odd:.2f} → garante "
                        f"R$ {hedge_calc.guaranteed_return:.2f} independente do resultado."
                    )

    elif ev_remaining > _EV_SHIFT_TRIGGER:
        action = "hold"
        urgency = "low"
        reasoning = (
            f"EV +{ev_remaining:.0%} — chance real {prob_current:.1%} vs implícita "
            f"{prob_at_entry:.1%}. Aposta com valor. Manter."
        )
    else:
        action = "hold"
        urgency = "medium"
        reasoning = (
            f"EV marginal ({ev_remaining:+.0%}). Monitorar — se cair mais, proteger."
        )

    # Verificação de fim de jogo (> minuto 85)
    if minute >= 85 and action == "hold" and prob_current < 0.5:
        action = "cashout"
        urgency = "high"
        reasoning = (
            f"Fim de jogo (min {minute}) com chance {prob_current:.1%}. "
            f"Pouco tempo para reverter — cash-out recomendado."
        )

    return BetAdvice(
        bet_id=bet.get("id", ""),
        event_name=bet.get("event_name", ""),
        market=market,
        outcome=outcome,
        stake=stake,
        odds_placed=odds_placed,
        potential_return=potential_return,
        prob_current=prob_current,
        ev_remaining=ev_remaining,
        prob_at_entry=prob_at_entry,
        action=action,
        urgency=urgency,
        hedge=hedge_suggestion,
        cashout_value=cashout_value,
        reasoning=reasoning,
    )


def advise_open_bets(
    open_bets: list[dict[str, Any]],
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None = None,
    minute: int = 0,
    home_team: str = "",
    away_team: str = "",
) -> HedgeReport:
    """Analisa todas as apostas abertas do usuário para o evento atual.

    Filtra apenas apostas que pertencem ao evento (por home/away team match).
    Retorna relatório consolidado com sugestões por aposta.
    """
    # Filtrar apostas do evento atual
    relevant_bets = []
    for bet in open_bets:
        bet_home = (bet.get("home_team") or "").lower()
        bet_away = (bet.get("away_team") or "").lower()
        event_name = (bet.get("event_name") or "").lower()

        # Match por time ou event_name
        if (
            (home_team.lower() in bet_home or home_team.lower() in event_name)
            and (away_team.lower() in bet_away or away_team.lower() in event_name)
        ) or (
            home_team.lower() in event_name and away_team.lower() in event_name
        ):
            relevant_bets.append(bet)

    if not relevant_bets:
        return HedgeReport(summary="Nenhuma aposta aberta para este evento.")

    # Deduplicar (mesma stake + odds + market = duplicata de captura)
    seen = set()
    unique_bets = []
    for bet in relevant_bets:
        picks = bet.get("picks") or []
        pick_key = (
            bet.get("stake"),
            bet.get("odds_placed"),
            picks[0].get("market") if picks else "",
            picks[0].get("outcome") if picks else "",
        )
        if pick_key not in seen:
            seen.add(pick_key)
            unique_bets.append(bet)

    # Analisar cada aposta
    advices = []
    for bet in unique_bets:
        advice = advise_single_bet(bet, inplay, snapshot, minute)
        advices.append(advice)

    # Consolidar
    total_risk = sum(a.stake for a in advices)
    total_potential = sum(a.potential_return for a in advices)
    critical_count = sum(1 for a in advices if a.urgency == "critical")
    high_count = sum(1 for a in advices if a.urgency == "high")

    if critical_count > 0:
        overall = "cashout"
        summary = f"⚠️ {critical_count} aposta(s) em risco crítico! Cash-out recomendado."
    elif high_count > 0:
        overall = "hedge"
        summary = f"🛡️ {high_count} aposta(s) precisam de proteção. Considere hedge."
    else:
        overall = "hold"
        summary = f"✓ {len(advices)} aposta(s) monitoradas — sem ação urgente."

    return HedgeReport(
        advices=advices,
        total_at_risk=total_risk,
        total_potential=total_potential,
        overall_action=overall,
        summary=summary,
    )


def hedge_report_to_dict(report: HedgeReport) -> dict[str, Any]:
    """Serializa HedgeReport para JSON (resposta da API)."""
    advices_list = []
    for a in report.advices:
        item: dict[str, Any] = {
            "bet_id": a.bet_id,
            "event_name": a.event_name,
            "market": a.market,
            "outcome": a.outcome,
            "stake": a.stake,
            "odds_placed": a.odds_placed,
            "potential_return": a.potential_return,
            "prob_current": round(a.prob_current, 4),
            "ev_remaining": round(a.ev_remaining, 4),
            "action": a.action,
            "urgency": a.urgency,
            "reasoning": a.reasoning,
        }
        if a.hedge:
            item["hedge"] = {
                "market": a.hedge.market,
                "outcome": a.hedge.outcome,
                "odd_current": a.hedge.odd_current,
                "stake_suggested": a.hedge.stake_suggested,
                "guaranteed_return": a.hedge.guaranteed_return,
                "net_if_original_wins": a.hedge.net_if_original_wins,
                "net_if_hedge_wins": a.hedge.net_if_hedge_wins,
            }
        if a.cashout_value:
            item["cashout_value"] = a.cashout_value
        advices_list.append(item)

    return {
        "advices": advices_list,
        "total_at_risk": report.total_at_risk,
        "total_potential": report.total_potential,
        "overall_action": report.overall_action,
        "summary": report.summary,
    }
