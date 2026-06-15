"""Análise de performance de apostas do usuário.

Calcula métricas como ROI por mercado, faixa de odd, minuto do jogo,
padrões de perda recorrentes e sugestões de ajuste de estratégia.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de resultado
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MarketPerformance:
    """Performance por tipo de mercado (h2h, totals, btts, etc.)."""

    market: str
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    cashouts: int = 0
    total_stake: float = 0.0
    total_return: float = 0.0
    roi_pct: float = 0.0
    avg_odd: float = 0.0
    win_rate_pct: float = 0.0


@dataclass
class OddRangePerformance:
    """Performance por faixa de odd."""

    range_label: str  # ex: "1.0–1.5", "1.5–2.0", "2.0–3.0", "3.0–5.0", "5.0+"
    range_min: float = 0.0
    range_max: float = 999.0
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    total_stake: float = 0.0
    total_return: float = 0.0
    roi_pct: float = 0.0
    win_rate_pct: float = 0.0


@dataclass
class LossPattern:
    """Padrão de perda identificado."""

    pattern_type: str  # "market_overbet", "high_odds_bias", "chasing_losses", etc.
    description: str
    severity: str  # "low", "medium", "high"
    evidence: str  # dados que sustentam o diagnóstico
    suggestion: str  # ação sugerida


@dataclass
class PerformanceReport:
    """Relatório completo de performance de apostas."""

    total_bets: int = 0
    total_stake: float = 0.0
    total_return: float = 0.0
    net_profit: float = 0.0
    roi_pct: float = 0.0
    win_rate_pct: float = 0.0
    avg_odd: float = 0.0
    best_market: str = ""
    worst_market: str = ""
    by_market: list[MarketPerformance] = field(default_factory=list)
    by_odd_range: list[OddRangePerformance] = field(default_factory=list)
    loss_patterns: list[LossPattern] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Funções auxiliares
# ──────────────────────────────────────────────────────────────────────────────

# Faixas de odd padrão para análise
ODD_RANGES = [
    ("1.01–1.50", 1.01, 1.50),
    ("1.50–2.00", 1.50, 2.00),
    ("2.00–3.00", 2.00, 3.00),
    ("3.00–5.00", 3.00, 5.00),
    ("5.00–10.0", 5.00, 10.0),
    ("10.0+", 10.0, 9999.0),
]


def _calculate_return(bet: dict[str, Any]) -> float:
    """Calcula o retorno real de uma aposta."""
    result = bet.get("result", "lost")
    stake = bet.get("stake", 0.0)
    potential = bet.get("potential_return", 0.0)
    cashout_val = bet.get("cashout_value")

    if result == "won":
        return potential if potential > 0 else stake * bet.get("odds_placed", 1.0)
    elif result == "cashout":
        return cashout_val if cashout_val else 0.0
    elif result == "void":
        return stake  # reembolso
    else:
        return 0.0


def _get_primary_market(bet: dict[str, Any]) -> str:
    """Extrai o mercado principal da aposta."""
    picks = bet.get("picks", [])
    if not picks:
        return "unknown"
    # Para combos, junta os mercados
    markets = set()
    for p in picks:
        m = p.get("market", "unknown") if isinstance(p, dict) else "unknown"
        # Normalizar: totals_2.5 → totals
        base_market = m.split("_")[0] if "_" in m and m[0] != "h" else m
        if base_market.startswith("totals"):
            base_market = "totals"
        markets.add(base_market)
    if len(markets) == 1:
        return markets.pop()
    return "combo"


def _get_odd_range_label(odd: float) -> str:
    """Retorna o label da faixa de odd."""
    for label, low, high in ODD_RANGES:
        if low <= odd < high:
            return label
    return "10.0+"


# ──────────────────────────────────────────────────────────────────────────────
# Análise principal
# ──────────────────────────────────────────────────────────────────────────────


def analyze_performance(settled_bets: list[dict[str, Any]]) -> PerformanceReport:
    """Analisa a performance do usuário com base em apostas liquidadas.

    Args:
        settled_bets: lista de dicts com campos: result, stake, odds_placed,
                      potential_return, cashout_value, picks, etc.

    Returns:
        PerformanceReport com métricas e padrões detectados.
    """
    if not settled_bets:
        return PerformanceReport()

    report = PerformanceReport()
    report.total_bets = len(settled_bets)

    # ─── Métricas globais ───
    total_stake = 0.0
    total_return = 0.0
    total_odds = 0.0
    wins = 0

    for bet in settled_bets:
        stake = bet.get("stake", 0.0)
        odd = bet.get("odds_placed", 0.0)
        ret = _calculate_return(bet)
        result = bet.get("result", "lost")

        total_stake += stake
        total_return += ret
        total_odds += odd
        if result == "won":
            wins += 1

    report.total_stake = round(total_stake, 2)
    report.total_return = round(total_return, 2)
    report.net_profit = round(total_return - total_stake, 2)
    report.roi_pct = round(
        ((total_return - total_stake) / total_stake * 100) if total_stake > 0 else 0, 2
    )
    report.win_rate_pct = round(wins / len(settled_bets) * 100, 2)
    report.avg_odd = round(total_odds / len(settled_bets), 2) if settled_bets else 0

    # ─── Performance por mercado ───
    market_stats: dict[str, dict[str, Any]] = {}
    for bet in settled_bets:
        market = _get_primary_market(bet)
        if market not in market_stats:
            market_stats[market] = {
                "total": 0, "wins": 0, "losses": 0, "cashouts": 0,
                "stake": 0.0, "return": 0.0, "odds_sum": 0.0,
            }
        ms = market_stats[market]
        ms["total"] += 1
        ms["stake"] += bet.get("stake", 0.0)
        ms["return"] += _calculate_return(bet)
        ms["odds_sum"] += bet.get("odds_placed", 0.0)
        result = bet.get("result", "lost")
        if result == "won":
            ms["wins"] += 1
        elif result == "cashout":
            ms["cashouts"] += 1
        else:
            ms["losses"] += 1

    for market, ms in market_stats.items():
        mp = MarketPerformance(
            market=market,
            total_bets=ms["total"],
            wins=ms["wins"],
            losses=ms["losses"],
            cashouts=ms["cashouts"],
            total_stake=round(ms["stake"], 2),
            total_return=round(ms["return"], 2),
            roi_pct=round(
                ((ms["return"] - ms["stake"]) / ms["stake"] * 100) if ms["stake"] > 0 else 0, 2
            ),
            avg_odd=round(ms["odds_sum"] / ms["total"], 2) if ms["total"] > 0 else 0,
            win_rate_pct=round(ms["wins"] / ms["total"] * 100, 2) if ms["total"] > 0 else 0,
        )
        report.by_market.append(mp)

    # Ordenar por ROI (melhor para pior)
    report.by_market.sort(key=lambda m: m.roi_pct, reverse=True)
    if report.by_market:
        report.best_market = report.by_market[0].market
        report.worst_market = report.by_market[-1].market

    # ─── Performance por faixa de odd ───
    range_stats: dict[str, dict[str, Any]] = {}
    for bet in settled_bets:
        odd = bet.get("odds_placed", 0.0)
        label = _get_odd_range_label(odd)
        if label not in range_stats:
            range_stats[label] = {"total": 0, "wins": 0, "losses": 0, "stake": 0.0, "return": 0.0}
        rs = range_stats[label]
        rs["total"] += 1
        rs["stake"] += bet.get("stake", 0.0)
        rs["return"] += _calculate_return(bet)
        if bet.get("result") == "won":
            rs["wins"] += 1
        else:
            rs["losses"] += 1

    for label, low, high in ODD_RANGES:
        if label in range_stats:
            rs = range_stats[label]
            orp = OddRangePerformance(
                range_label=label,
                range_min=low,
                range_max=high,
                total_bets=rs["total"],
                wins=rs["wins"],
                losses=rs["losses"],
                total_stake=round(rs["stake"], 2),
                total_return=round(rs["return"], 2),
                roi_pct=round(
                    ((rs["return"] - rs["stake"]) / rs["stake"] * 100)
                    if rs["stake"] > 0 else 0, 2
                ),
                win_rate_pct=round(
                    rs["wins"] / rs["total"] * 100 if rs["total"] > 0 else 0, 2
                ),
            )
            report.by_odd_range.append(orp)

    # ─── Detecção de padrões de perda ───
    report.loss_patterns = _detect_loss_patterns(settled_bets, market_stats, range_stats)

    # ─── Sugestões ───
    report.suggestions = _generate_suggestions(report)

    return report


# ──────────────────────────────────────────────────────────────────────────────
# Detecção de padrões de perda
# ──────────────────────────────────────────────────────────────────────────────


def _detect_loss_patterns(
    bets: list[dict[str, Any]],
    market_stats: dict[str, Any],
    range_stats: dict[str, Any],
) -> list[LossPattern]:
    """Identifica padrões recorrentes de perda."""
    patterns: list[LossPattern] = []

    # 1. Bias por odds altas (aposta frequente em >3.0 com ROI negativo)
    high_odds_bets = [b for b in bets if b.get("odds_placed", 0) >= 3.0]
    if len(high_odds_bets) >= 3:
        high_stake = sum(b.get("stake", 0) for b in high_odds_bets)
        high_return = sum(_calculate_return(b) for b in high_odds_bets)
        high_roi = ((high_return - high_stake) / high_stake * 100) if high_stake > 0 else 0
        if high_roi < -20:
            patterns.append(LossPattern(
                pattern_type="high_odds_bias",
                description="Preferência por odds altas com retorno negativo",
                severity="high" if high_roi < -50 else "medium",
                evidence=(
                    f"{len(high_odds_bets)} apostas em odds >= 3.0, "
                    f"ROI = {high_roi:.1f}%, "
                    f"perda total = R$ {high_stake - high_return:.2f}"
                ),
                suggestion=(
                    "Reduzir exposição em odds altas (>3.0). "
                    "Focar em mercados com odds 1.5–2.5 onde a taxa de acerto justifica o risco."
                ),
            ))

    # 2. Overbet em mercado ruim (>30% das apostas num mercado com ROI < -30%)
    total_bets = len(bets)
    for market, ms in market_stats.items():
        roi = ((ms["return"] - ms["stake"]) / ms["stake"] * 100) if ms["stake"] > 0 else 0
        share = ms["total"] / total_bets if total_bets > 0 else 0
        if share > 0.25 and roi < -30 and ms["total"] >= 3:
            patterns.append(LossPattern(
                pattern_type="market_overbet",
                description=f"Concentração excessiva no mercado '{market}' com resultado ruim",
                severity="high" if roi < -50 else "medium",
                evidence=(
                    f"{ms['total']} apostas ({share*100:.0f}% do total) em '{market}', "
                    f"ROI = {roi:.1f}%, win rate = {ms['wins']/ms['total']*100:.0f}%"
                ),
                suggestion=(
                    f"Diversificar: mercado '{market}' está gerando prejuízo consistente. "
                    "Considere reduzir stake ou trocar para mercado com melhor histórico."
                ),
            ))

    # 3. Chasing losses (stake crescente após sequência de derrotas)
    sorted_bets = sorted(bets, key=lambda b: b.get("settled_at", ""))
    consecutive_losses = 0
    chase_detected = False
    prev_stake = 0.0
    for bet in sorted_bets:
        if bet.get("result") == "lost":
            consecutive_losses += 1
            current_stake = bet.get("stake", 0)
            if consecutive_losses >= 3 and current_stake > prev_stake * 1.5 and prev_stake > 0:
                chase_detected = True
            prev_stake = current_stake
        else:
            consecutive_losses = 0
            prev_stake = bet.get("stake", 0)

    if chase_detected:
        patterns.append(LossPattern(
            pattern_type="chasing_losses",
            description="Padrão de martingale detectado — stake aumenta após derrotas",
            severity="high",
            evidence=(
                "Sequências de 3+ derrotas consecutivas com aumento de stake >50% "
                "entre apostas adjacentes."
            ),
            suggestion=(
                "Manter stake fixo independente de resultados anteriores. "
                "Usar Kelly fraction para calcular stake ótimo baseado em EV, não em emoção."
            ),
        ))

    # 4. Over-totals bias (aposta frequente em Over sem acerto)
    over_bets = [
        b for b in bets
        if any(
            (p.get("outcome", "") == "over" if isinstance(p, dict) else False)
            for p in b.get("picks", [])
        )
    ]
    if len(over_bets) >= 3:
        over_wins = sum(1 for b in over_bets if b.get("result") == "won")
        over_wr = over_wins / len(over_bets) if over_bets else 0
        if over_wr < 0.3:
            patterns.append(LossPattern(
                pattern_type="over_totals_bias",
                description="Viés para 'Over' em totais com taxa de acerto baixa",
                severity="medium",
                evidence=(
                    f"{len(over_bets)} apostas em Over, "
                    f"win rate = {over_wr*100:.0f}% (abaixo de 30%)"
                ),
                suggestion=(
                    "Considerar Under em jogos defensivos ou com ataque fraco. "
                    "O mercado de totais exige análise de estilo tático, não apenas 'intuição'."
                ),
            ))

    # 5. Apostas em favorito perdendo (ao vivo)
    losing_fav_bets = [
        b for b in bets
        if any(
            (p.get("outcome", "") in ("home", "away", "1", "2") if isinstance(p, dict) else False)
            for p in b.get("picks", [])
        )
        and b.get("odds_placed", 0) > 3.0
        and b.get("result") == "lost"
    ]
    if len(losing_fav_bets) >= 2:
        total_loss = sum(b.get("stake", 0) for b in losing_fav_bets)
        patterns.append(LossPattern(
            pattern_type="value_trap",
            description="Apostas em resultado final com odds altas (time perdendo) = value trap",
            severity="medium",
            evidence=(
                f"{len(losing_fav_bets)} apostas perdidas em h2h com odds > 3.0, "
                f"perda = R$ {total_loss:.2f}"
            ),
            suggestion=(
                "Odds altas em resultado final indicam que o time está em desvantagem. "
                "Preferir cash-out ou hedge ao invés de esperar virada improvável."
            ),
        ))

    return patterns


# ──────────────────────────────────────────────────────────────────────────────
# Sugestões baseadas no relatório
# ──────────────────────────────────────────────────────────────────────────────


def _generate_suggestions(report: PerformanceReport) -> list[str]:
    """Gera sugestões acionáveis com base nas métricas."""
    suggestions: list[str] = []

    # ROI geral negativo
    if report.roi_pct < -10:
        suggestions.append(
            f"ROI geral de {report.roi_pct:.1f}% indica necessidade de ajuste. "
            "Revise os mercados e faixas de odd onde perde mais."
        )

    # Win rate muito baixa
    if report.win_rate_pct < 30 and report.total_bets >= 5:
        suggestions.append(
            f"Win rate de {report.win_rate_pct:.0f}% está abaixo do saudável. "
            "Considere odds menores (1.5–2.0) para aumentar frequência de acerto."
        )

    # Odd média muito alta
    if report.avg_odd > 4.0 and report.total_bets >= 3:
        suggestions.append(
            f"Odd média de {report.avg_odd:.2f} é muito alta. "
            "Apostas em odds > 4.0 exigem win rate > 25% para break-even — revise se atinge isso."
        )

    # Melhor mercado vs pior
    if report.by_market and len(report.by_market) >= 2:
        best = report.by_market[0]
        worst = report.by_market[-1]
        if best.roi_pct > 0 and worst.roi_pct < -20:
            suggestions.append(
                f"Concentre em '{best.market}' (ROI +{best.roi_pct:.0f}%) "
                f"e reduza '{worst.market}' (ROI {worst.roi_pct:.0f}%)."
            )

    # Faixa de odd lucrativa
    profitable_ranges = [r for r in report.by_odd_range if r.roi_pct > 0 and r.total_bets >= 2]
    if profitable_ranges:
        best_range = max(profitable_ranges, key=lambda r: r.roi_pct)
        suggestions.append(
            f"Sua melhor faixa de odd é {best_range.range_label} "
            f"(ROI +{best_range.roi_pct:.0f}%, {best_range.wins}/{best_range.total_bets} wins). "
            "Considere aumentar stake nessa faixa."
        )

    # Muitos cashouts (pode indicar falta de confiança)
    total_cashouts = sum(m.cashouts for m in report.by_market)
    if total_cashouts > 0 and total_cashouts / report.total_bets > 0.3:
        suggestions.append(
            f"Alta taxa de cash-out ({total_cashouts}/{report.total_bets}). "
            "Cash-outs frequentes reduzem EV a longo prazo. "
            "Use apenas quando modelo indica EV < 0."
        )

    return suggestions


# ──────────────────────────────────────────────────────────────────────────────
# Utilitário: resumo compacto para API
# ──────────────────────────────────────────────────────────────────────────────


def performance_report_to_dict(report: PerformanceReport) -> dict[str, Any]:
    """Converte o relatório para dicionário serializável (JSON-friendly)."""
    return {
        "summary": {
            "total_bets": report.total_bets,
            "total_stake": report.total_stake,
            "total_return": report.total_return,
            "net_profit": report.net_profit,
            "roi_pct": report.roi_pct,
            "win_rate_pct": report.win_rate_pct,
            "avg_odd": report.avg_odd,
            "best_market": report.best_market,
            "worst_market": report.worst_market,
        },
        "by_market": [
            {
                "market": m.market,
                "total_bets": m.total_bets,
                "wins": m.wins,
                "losses": m.losses,
                "cashouts": m.cashouts,
                "total_stake": m.total_stake,
                "total_return": m.total_return,
                "roi_pct": m.roi_pct,
                "avg_odd": m.avg_odd,
                "win_rate_pct": m.win_rate_pct,
            }
            for m in report.by_market
        ],
        "by_odd_range": [
            {
                "range": r.range_label,
                "total_bets": r.total_bets,
                "wins": r.wins,
                "losses": r.losses,
                "total_stake": r.total_stake,
                "total_return": r.total_return,
                "roi_pct": r.roi_pct,
                "win_rate_pct": r.win_rate_pct,
            }
            for r in report.by_odd_range
        ],
        "loss_patterns": [
            {
                "type": p.pattern_type,
                "description": p.description,
                "severity": p.severity,
                "evidence": p.evidence,
                "suggestion": p.suggestion,
            }
            for p in report.loss_patterns
        ],
        "suggestions": report.suggestions,
    }
