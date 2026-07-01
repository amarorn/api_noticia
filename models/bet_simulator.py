"""Simulador de apostas com alertas inteligentes baseados no histórico do usuário.

Permite simular uma aposta antes de colocar na Superbet, verificando:
- Padrões de perda recorrentes do usuário
- Contradições lógicas (ex: apostar em 1 e 2 no mesmo jogo)
- EV estimado
- Compatibilidade com histórico lucrativo

Retorna: score, alertas, recomendação, e ações sugeridas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class BetAlert:
    """Um alerta sobre a aposta simulada."""

    level: str          # "critical" | "warning" | "info" | "success"
    code: str           # identificador do alerta
    title: str          # título curto
    message: str        # descrição completa
    suggestion: str     # o que fazer


@dataclass
class SimulatedBetResult:
    """Resultado da simulação de uma aposta."""

    is_valid: bool = True
    score: float = 0.0          # 0-100
    recommendation: str = ""    # "GO" | "CAUTION" | "STOP"
    ev_estimate: float = 0.0
    alerts: list[BetAlert] = field(default_factory=list)
    potential_return: float = 0.0
    risk_level: str = "medium"  # "low" | "medium" | "high" | "extreme"


# ──────────────────────────────────────────────────────────────────────────────
# Análise de padrões de perda
# ──────────────────────────────────────────────────────────────────────────────


def _load_settled_bets() -> list[dict[str, Any]]:
    from api.user_bets_store import list_settled_bets
    bets = list_settled_bets()
    return [b.model_dump(mode="json") for b in bets]


def _get_market_from_pick(pick: dict[str, Any]) -> str:
    m = pick.get("market", "unknown")
    if m.startswith("totals"):
        return "totals"
    return m.split("_")[0] if "_" in m else m


def _analyze_loss_patterns(settled_bets: list[dict[str, Any]]) -> dict[str, Any]:
    """Extrai padrões de perda do histórico."""
    lost = [b for b in settled_bets if b.get("result") == "lost"]
    if not lost:
        return {"has_data": False}

    patterns = {
        "has_data": True,
        "total_lost": len(lost),
        "total_lost_stake": sum(b.get("stake", 0) for b in lost),
        "markets": {},
        "odd_ranges": {},
        "events": {},
        "combos": {"simples": 0, "combo": 0},
        "h2h_both_sides": [],
    }

    for b in lost:
        odd = b.get("odds_placed", 0)
        picks = b.get("picks", []) or []
        event = b.get("event_name", "")
        stake = b.get("stake", 0)

        # Por mercado
        for p in picks:
            m = _get_market_from_pick(p)
            if m not in patterns["markets"]:
                patterns["markets"][m] = {"count": 0, "stake": 0.0, "odds": []}
            patterns["markets"][m]["count"] += 1
            patterns["markets"][m]["stake"] += stake / len(picks)
            patterns["markets"][m]["odds"].append(odd)

        # Por faixa de odd
        if odd < 2.0:
            rng = "1.0-2.0"
        elif odd < 3.0:
            rng = "2.0-3.0"
        elif odd < 5.0:
            rng = "3.0-5.0"
        else:
            rng = "5.0+"
        if rng not in patterns["odd_ranges"]:
            patterns["odd_ranges"][rng] = {"count": 0, "stake": 0.0}
        patterns["odd_ranges"][rng]["count"] += 1
        patterns["odd_ranges"][rng]["stake"] += stake

        # Por evento
        if event:
            if event not in patterns["events"]:
                patterns["events"][event] = {"count": 0, "stake": 0.0, "results": []}
            patterns["events"][event]["count"] += 1
            patterns["events"][event]["stake"] += stake

        # Simples vs combo
        if len(picks) > 1:
            patterns["combos"]["combo"] += 1
        else:
            patterns["combos"]["simples"] += 1

    # Detectar apostas em ambos os lados do mesmo jogo (h2h)
    for event_name, event_data in patterns["events"].items():
        event_bets = [b for b in lost if b.get("event_name") == event_name]
        h2h_outcomes = set()
        for b in event_bets:
            for p in b.get("picks", []):
                if p.get("market") == "h2h":
                    h2h_outcomes.add(p.get("outcome", ""))
        if len(h2h_outcomes) > 1 and "1" in h2h_outcomes and "2" in h2h_outcomes:
            patterns["h2h_both_sides"].append(event_name)

    return patterns


# ──────────────────────────────────────────────────────────────────────────────
# Simulação principal
# ──────────────────────────────────────────────────────────────────────────────


def simulate_bet(
    picks: list[dict[str, Any]],
    stake: float,
    odds_placed: float,
    event_name: str,
    home_team: str,
    away_team: str,
    *,
    minute: int | None = None,
    superbet_event_id: int | None = None,
) -> SimulatedBetResult:
    """Simula uma aposta e retorna alertas + score.

    Args:
        picks: lista de palpites (market, outcome, etc.)
        stake: valor apostado
        odds_placed: odd total
        event_name: nome do evento
        home_team: mandante
        away_team: visitante
        minute: minuto do jogo (opcional)
        superbet_event_id: ID do evento na Superbet

    Returns:
        SimulatedBetResult com alertas, score e recomendação
    """
    result = SimulatedBetResult()
    result.potential_return = stake * odds_placed
    alerts: list[BetAlert] = []
    score = 50.0  # base

    settled = _load_settled_bets()
    loss_patterns = _analyze_loss_patterns(settled)

    n_legs = len(picks)

    # ─── 1. Validações CRÍTICAS (podem invalidar a aposta) ───

    # 1.1 Contradição lógica: h2h 1 e h2h 2 no mesmo bilhete
    h2h_outcomes = set()
    for p in picks:
        if p.get("market") == "h2h":
            h2h_outcomes.add(p.get("outcome", ""))
    if "1" in h2h_outcomes and "2" in h2h_outcomes:
        alerts.append(BetAlert(
            level="critical",
            code="CONTRADICTORY_H2H",
            title="Contradição lógica no bilhete",
            message="Você apostou na vitória do mandante (1) E do visitante (2) no mesmo jogo. Isso é impossível — um dos dois perde com certeza.",
            suggestion="Remova uma das pernas de h2h. Escolha apenas um lado ou use dupla chance.",
        ))
        result.is_valid = False
        score -= 40

    # 1.2 Contradição: over e under no mesmo total
    over_lines = set()
    under_lines = set()
    for p in picks:
        m = p.get("market", "")
        if "over" in m.lower():
            over_lines.add(m)
        if "under" in m.lower():
            under_lines.add(m)
    if over_lines and under_lines:
        alerts.append(BetAlert(
            level="critical",
            code="CONTRADICTORY_TOTALS",
            title="Over e Under no mesmo bilhete",
            message="Apostou em 'Mais de' e 'Menos de' gols simultaneamente. Se um ganha, o outro perde.",
            suggestion="Escolha apenas uma direção (Over OU Under), nunca ambas.",
        ))
        result.is_valid = False
        score -= 30

    # 1.3 Aposta em ambos os lados do mesmo jogo (histórico)
    if loss_patterns.get("has_data"):
        if event_name in loss_patterns.get("h2h_both_sides", []):
            alerts.append(BetAlert(
                level="critical",
                code="BOTH_SIDES_HISTORY",
                title="⚠️ Você já se auto-contrariou neste jogo!",
                message=f"Você já perdeu apostando em ambos os lados de '{event_name}'. É um padrão de perda recorrente.",
                suggestion="NUNCA aposte em 1 e 2 no mesmo jogo. Escolha um lado baseado no modelo.",
            ))
            score -= 25

    # ─── 2. Alertas de Padrão de Perda (WARNING) ───

    if loss_patterns.get("has_data"):
        # 2.1 Mercado com histórico ruim
        for p in picks:
            m = _get_market_from_pick(p)
            if m in loss_patterns.get("markets", {}):
                mstats = loss_patterns["markets"][m]
                if mstats["count"] >= 3:
                    avg_odd = sum(mstats["odds"]) / len(mstats["odds"])
                    alerts.append(BetAlert(
                        level="warning",
                        code="LOSING_MARKET",
                        title=f"Mercado '{m}' tem histórico negativo",
                        message=f"Você já perdeu {mstats['count']}x em '{m}', totalizando R$ {mstats['stake']:.2f}.",
                        suggestion=f"Considere trocar de mercado. Sua média de odd nesse mercado foi {avg_odd:.2f}.",
                    ))
                    score -= 10

        # 2.2 Faixa de odd com histórico ruim
        if odds_placed >= 5.0:
            high_odds = loss_patterns["odd_ranges"].get("5.0+", {})
            if high_odds.get("count", 0) >= 2:
                alerts.append(BetAlert(
                    level="warning",
                    code="HIGH_ODDS_TRAP",
                    title="🪤 Odds altas = armadilha para você",
                    message=f"Você já perdeu {high_odds['count']}x em odds > 5.0 (R$ {high_odds['stake']:.2f}). Win rate nessa faixa é muito baixo.",
                    suggestion="Odds > 5.0 parecem valor mas são 'value traps'. Foque em odds 1.5-3.0.",
                ))
                score -= 15

        # 2.3 Evento já muito apostado e perdido
        event_data = loss_patterns.get("events", {}).get(event_name)
        if event_data and event_data["count"] >= 2:
            alerts.append(BetAlert(
                level="warning",
                code="EVENT_CHASING",
                title="Você está 'perseguindo' este jogo",
                message=f"Já perdeu {event_data['count']}x em '{event_name}' (R$ {event_data['stake']:.2f}).",
                suggestion="Não tente 'recuperar' no mesmo jogo. O mercado não deve emoção. Passe para outro evento.",
            ))
            score -= 12

        # 2.4 Combos com histórico ruim
        if n_legs > 1:
            combo_lost = loss_patterns["combos"]["combo"]
            simples_lost = loss_patterns["combos"]["simples"]
            total = combo_lost + simples_lost
            if total > 0 and combo_lost / total > 0.5:
                alerts.append(BetAlert(
                    level="warning",
                    code="COMBO_LOSER",
                    title="Combos têm pior histórico que simples",
                    message=f"{combo_lost} combos perdidos vs {simples_lost} simples. Cada perna extra multiplica o risco.",
                    suggestion="Prefira apostas simples. Se usar combo, máximo 2 pernas e com correlação positiva.",
                ))
                score -= 8

    # ─── 3. Análise de EV ───

    # Estimativa de EV baseada na odd
    if odds_placed > 1:
        prob_est = (1.0 / odds_placed) * 0.85  # overround ajustado
        ev = prob_est * odds_placed - 1.0
        result.ev_estimate = round(ev, 3)

        if ev >= 0.1:
            alerts.append(BetAlert(
                level="success",
                code="POSITIVE_EV",
                title="EV positivo estimado",
                message=f"EV estimado: +{ev:.1%}. A longo prazo, apostas com EV > 0 geram lucro.",
                suggestion="Boa aposta estatisticamente. Mantenha stake controlado.",
            ))
            score += 15
        elif ev >= 0:
            alerts.append(BetAlert(
                level="info",
                code="BREAKEVEN_EV",
                title="EV próximo de zero",
                message=f"EV estimado: {ev:.1%}. Sem vantagem clara, mas sem prejuízo esperado.",
                suggestion="Aceitável se for 'aposta de valor' com informação privilegiada.",
            ))
            score += 5
        else:
            alerts.append(BetAlert(
                level="warning",
                code="NEGATIVE_EV",
                title="EV negativo — a casa tem vantagem",
                message=f"EV estimado: {ev:.1%}. A matemática está contra você nesta aposta.",
                suggestion="Reconsidere. Apenas aposte com EV negativo se tiver edge real (info privilegiada).",
            ))
            score -= 10

    # ─── 4. Análise de odd ───

    if odds_placed < 1.5:
        alerts.append(BetAlert(
            level="warning",
            code="LOW_ODD",
            title="Odd muito baixa",
            message=f"Odd {odds_placed} é muito baixa — risco não compensa o retorno.",
            suggestion="Odds < 1.5 exigem win rate > 67% para lucro. Tem certeza dessa probabilidade?",
        ))
        score -= 5
    elif odds_placed > 10.0:
        alerts.append(BetAlert(
            level="warning",
            code="EXTREME_ODD",
            title="Odd extremamente alta",
            message=f"Odd {odds_placed} — win rate necessário: {100/odds_placed:.1f}%.",
            suggestion="Odds > 10 são loteria. Use stake mínimo (R$ 2-5) apenas.",
        ))
        score -= 10

    # ─── 5. Análise de stake ───

    if stake > 50:
        alerts.append(BetAlert(
            level="warning",
            code="HIGH_STAKE",
            title="Stake alto",
            message=f"R$ {stake:.2f} é um stake elevado. Perdas consecutivas com stakes altos aceleram a quebra.",
            suggestion="Use no máximo 5% da banca por aposta. Se sua banca é R$ 500, stake ideal = R$ 25.",
        ))
        score -= 5

    # ─── 6. Timing ───

    if minute is not None:
        if minute < 15:
            alerts.append(BetAlert(
                level="info",
                code="EARLY_BET",
                title="Aposta muito cedo no jogo",
                message=f"Minuto {minute} — jogo ainda se definindo. Incerteza alta.",
                suggestion="Espere até o minuto 20-30 para ter melhor leitura do jogo.",
            ))
            score -= 3
        elif minute > 80:
            alerts.append(BetAlert(
                level="info",
                code="LATE_BET",
                title="Aposta muito tardia",
                message=f"Minuto {minute} — pouco tempo para o evento ocorrer.",
                suggestion="Odds em minutos finais geralmente não têm valor. Prefira mercados de resultado final.",
            ))
            score -= 3
        elif 30 <= minute <= 70:
            alerts.append(BetAlert(
                level="success",
                code="GOOD_TIMING",
                title="Timing ideal",
                message=f"Minuto {minute} — jogo já definido, ainda com tempo para viradas.",
                suggestion="Sweet spot para apostas ao vivo. Boa escolha de timing.",
            ))
            score += 5

    # ─── Score final e recomendação ───

    score = max(0, min(100, score))
    result.score = round(score, 1)

    if score >= 70:
        result.recommendation = "GO"
        result.risk_level = "low"
        if not any(a.level == "critical" for a in alerts):
            alerts.insert(0, BetAlert(
                level="success",
                code="GOOD_BET",
                title="✅ Aposta aprovada pelo simulador",
                message=f"Score {score:.0f}/100 — EV positivo, sem contradições, alinhada com histórico.",
                suggestion="Prossiga com confiança. Mantenha stake dentro do planejado.",
            ))
    elif score >= 45:
        result.recommendation = "CAUTION"
        result.risk_level = "medium"
        alerts.insert(0, BetAlert(
            level="warning",
            code="CAUTION",
            title="⚠️ Aposta com ressalvas",
            message=f"Score {score:.0f}/100 — há alertas que merecem atenção.",
            suggestion="Reavalie os pontos destacados. Se decidir apostar, reduza o stake.",
        ))
    else:
        result.recommendation = "STOP"
        result.risk_level = "high" if score >= 25 else "extreme"
        alerts.insert(0, BetAlert(
            level="critical",
            code="STOP",
            title="🛑 NÃO APOSTE",
            message=f"Score {score:.0f}/100 — múltiplos problemas detectados.",
            suggestion="Esta aposta repete padrões que já te fizeram perder. Passe para outra oportunidade.",
        ))

    result.alerts = alerts
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Serialização
# ──────────────────────────────────────────────────────────────────────────────


def simulation_result_to_dict(result: SimulatedBetResult) -> dict[str, Any]:
    return {
        "is_valid": result.is_valid,
        "score": result.score,
        "recommendation": result.recommendation,
        "ev_estimate": result.ev_estimate,
        "potential_return": result.potential_return,
        "risk_level": result.risk_level,
        "alerts": [
            {
                "level": a.level,
                "code": a.code,
                "title": a.title,
                "message": a.message,
                "suggestion": a.suggestion,
            }
            for a in result.alerts
        ],
    }
