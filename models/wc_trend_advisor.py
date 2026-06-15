"""Analisador de tendência do jogo ao vivo — copiloto de posição.

Fluxo:
  1. Lê múltiplos snapshots (ticks) do evento ao longo do tempo
  2. Detecta tendências: placar acelerando, mercado colapsando, dominação
  3. Compara a posição do usuário (aposta) contra a tendência
  4. Emite: SAIR | MANTER | REPOSICIONAR → com direção concreta

Diferença do hedge_advisor (EV mecânico):
  Este módulo analisa o FLUXO DO JOGO — não apenas probabilidades estáticas.
  Ele lê sinais como:
    - Gols consecutivos do mesmo time (domínio)
    - Odds colapsando (mercado "concordando" que algo é certo)
    - Mercados fechando (Superbet já decidiu o outcome)
    - Minuto + placar gap = tempo insuficiente para virada
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class GameTick:
    """Um snapshot do jogo num dado momento."""

    minute: int = 0
    home_score: int = 0
    away_score: int = 0
    total_goals: int = 0
    home_generosity: float = 0.5
    away_generosity: float = 0.5
    over_implied: dict[str, float] = field(default_factory=dict)  # "3.5" → 0.73
    h2h_implied: dict[str, float] = field(default_factory=dict)   # "1" → 0.80
    next_goal_home_odd: float | None = None
    next_goal_away_odd: float | None = None
    markets_open: int = 0
    captured_at: str = ""


@dataclass
class TrendSignal:
    """Um sinal de tendência detectado."""

    signal_type: str  # "score_gap", "domination", "market_collapse", "goal_rush", etc.
    direction: str    # "home_winning", "over", "under", "draw_dying", etc.
    strength: float   # 0.0–1.0 (quão forte é o sinal)
    description: str  # explicação em português
    minute: int = 0


@dataclass
class PositionAdvice:
    """Conselho sobre a posição do usuário."""

    action: str         # "exit" | "hold" | "reposition"
    urgency: str        # "critical" | "high" | "medium" | "low"
    reasoning: str      # por quê (português)
    reposition_to: str | None = None   # mercado sugerido para reposicionar
    reposition_detail: str | None = None  # detalhe (ex: "Over 5.5 @ 1.33")
    reposition_odd: float | None = None
    confidence: float = 0.0  # 0–1 quão confiante na sugestão


@dataclass
class GameTrendReport:
    """Relatório completo de tendência + conselho de posição."""

    event_id: int = 0
    home_team: str = ""
    away_team: str = ""
    current_score: str = ""
    minute: int = 0
    signals: list[TrendSignal] = field(default_factory=list)
    dominant_trend: str = ""  # resumo da tendência dominante
    position_advice: PositionAdvice | None = None
    best_opportunities: list[dict[str, Any]] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Parsing de ticks
# ──────────────────────────────────────────────────────────────────────────────


def parse_tick(raw: dict[str, Any]) -> GameTick:
    """Converte um snapshot raw (JSON) em GameTick estruturado."""
    inplay = raw.get("inplay") or {}
    home_score = inplay.get("home_score", 0)
    away_score = inplay.get("away_score", 0)

    # Over implied probs (mapa linha → prob over)
    over_implied = {}
    totals_imp = raw.get("totals_implied") or {}
    for line, probs in totals_imp.items():
        for key, val in probs.items():
            if "mais" in key.lower() or "over" in key.lower():
                over_implied[str(line)] = val

    # H2H implied
    h2h_imp = raw.get("h2h_implied") or {}

    # Next goal odds
    ng = raw.get("next_goal_odds") or {}

    gen = raw.get("generosity_probs") or {}

    return GameTick(
        minute=inplay.get("minute", 0),
        home_score=home_score,
        away_score=away_score,
        total_goals=home_score + away_score,
        home_generosity=gen.get("home", 0.5),
        away_generosity=gen.get("away", 0.5),
        over_implied=over_implied,
        h2h_implied=h2h_imp,
        next_goal_home_odd=ng.get("home"),
        next_goal_away_odd=ng.get("away"),
        markets_open=raw.get("raw_market_count", 0),
        captured_at=raw.get("captured_at", ""),
    )


def load_event_ticks(event_dir: Path) -> list[GameTick]:
    """Carrega todos os ticks de um evento (exceto latest.json) em ordem cronológica."""
    import json

    ticks = []
    if not event_dir.exists():
        return ticks

    for f in sorted(event_dir.glob("2*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            ticks.append(parse_tick(raw))
        except Exception as e:
            logger.warning("Erro ao ler tick %s: %s", f.name, e)
    return ticks


# ──────────────────────────────────────────────────────────────────────────────
# Detecção de tendência
# ──────────────────────────────────────────────────────────────────────────────


def detect_trends(ticks: list[GameTick]) -> list[TrendSignal]:
    """Analisa a sequência de ticks e detecta sinais de tendência."""
    if len(ticks) < 2:
        return []

    signals: list[TrendSignal] = []
    latest = ticks[-1]
    first = ticks[0]

    # ─── 1. Placar gap (dominação por gols) ───
    score_diff = latest.home_score - latest.away_score
    if abs(score_diff) >= 2:
        dominant = "home" if score_diff > 0 else "away"
        team_label = "mandante" if dominant == "home" else "visitante"
        signals.append(TrendSignal(
            signal_type="score_gap",
            direction=f"{dominant}_dominating",
            strength=min(abs(score_diff) / 4, 1.0),
            description=(
                f"Placar {latest.home_score}×{latest.away_score} — "
                f"{team_label} domina por {abs(score_diff)} gol(s)."
            ),
            minute=latest.minute,
        ))

    # ─── 2. Goal rush (muitos gols em pouco tempo) ───
    if len(ticks) >= 3:
        recent_ticks = ticks[-4:]  # últimos ~8 minutos (a cada 2 min)
        goals_start = recent_ticks[0].total_goals
        goals_now = latest.total_goals
        goals_in_window = goals_now - goals_start
        if goals_in_window >= 2:
            signals.append(TrendSignal(
                signal_type="goal_rush",
                direction="over",
                strength=min(goals_in_window / 3, 1.0),
                description=(
                    f"{goals_in_window} gol(s) nos últimos minutos — "
                    f"jogo aberto, tendência Over."
                ),
                minute=latest.minute,
            ))

    # ─── 3. Gols concentrados em um time (dominação ofensiva) ───
    home_goals_2h = latest.home_score - (ticks[0].home_score if ticks else 0)
    away_goals_2h = latest.away_score - (ticks[0].away_score if ticks else 0)
    total_period_goals = home_goals_2h + away_goals_2h
    if total_period_goals >= 2:
        if home_goals_2h > 0 and away_goals_2h == 0:
            signals.append(TrendSignal(
                signal_type="one_side_scoring",
                direction="home_only",
                strength=min(home_goals_2h / 3, 1.0),
                description=(
                    f"Apenas mandante marcou no período monitorado "
                    f"({home_goals_2h} gol(s)). Visitante não ameaça."
                ),
                minute=latest.minute,
            ))
        elif away_goals_2h > 0 and home_goals_2h == 0:
            signals.append(TrendSignal(
                signal_type="one_side_scoring",
                direction="away_only",
                strength=min(away_goals_2h / 3, 1.0),
                description=(
                    f"Apenas visitante marcou no período monitorado "
                    f"({away_goals_2h} gol(s)). Mandante não ameaça."
                ),
                minute=latest.minute,
            ))

    # ─── 4. Generosity colapso (Superbet "decidiu") ───
    if latest.home_generosity >= 0.95 and latest.away_generosity < 0.01:
        signals.append(TrendSignal(
            signal_type="market_decided",
            direction="home_certain",
            strength=0.95,
            description=(
                "Superbet considera vitória mandante praticamente certa "
                f"(gen. mandante={latest.home_generosity:.1%}, "
                f"visitante={latest.away_generosity:.4%})."
            ),
            minute=latest.minute,
        ))
    elif latest.away_generosity >= 0.95 and latest.home_generosity < 0.01:
        signals.append(TrendSignal(
            signal_type="market_decided",
            direction="away_certain",
            strength=0.95,
            description=(
                "Superbet considera vitória visitante praticamente certa."
            ),
            minute=latest.minute,
        ))

    # ─── 5. Mercados desaparecendo (odds {} = Superbet removeu) ───
    if len(ticks) >= 2:
        prev = ticks[-2]
        if prev.markets_open > 5 and latest.markets_open <= 3:
            signals.append(TrendSignal(
                signal_type="market_collapse",
                direction="game_decided",
                strength=0.8,
                description=(
                    f"Mercados fechando: {prev.markets_open} → {latest.markets_open} "
                    f"disponíveis. Superbet retirando opções."
                ),
                minute=latest.minute,
            ))

    # ─── 6. Tempo + gap = irreversível ───
    remaining = 90 - latest.minute
    if remaining <= 20 and abs(score_diff) >= 2:
        signals.append(TrendSignal(
            signal_type="time_running_out",
            direction="result_locked",
            strength=min((abs(score_diff) * (90 - remaining)) / 200, 1.0),
            description=(
                f"Restam ~{remaining}min com {abs(score_diff)} gol(s) de diferença. "
                f"Virada estatisticamente improvável (<5%)."
            ),
            minute=latest.minute,
        ))

    # ─── 7. Over trend (odds Over caindo entre ticks = mercado espera mais gols) ───
    if len(ticks) >= 3:
        # Verificar se Over de alguma linha subiu muito em implied prob
        for line in latest.over_implied:
            if line in first.over_implied:
                delta = latest.over_implied[line] - first.over_implied[line]
                if delta > 0.15:  # implied subiu >15pp
                    signals.append(TrendSignal(
                        signal_type="over_trend",
                        direction="over",
                        strength=min(delta, 1.0),
                        description=(
                            f"Over {line} subiu de {first.over_implied[line]:.0%} → "
                            f"{latest.over_implied[line]:.0%} — mercado espera mais gols."
                        ),
                        minute=latest.minute,
                    ))

    # ─── 8. Draw morrendo (empate ficando improvável) ───
    if "X" in latest.h2h_implied and "X" in first.h2h_implied:
        draw_now = latest.h2h_implied.get("X", 0)
        draw_before = first.h2h_implied.get("X", 0)
        if draw_before > 0.10 and draw_now < 0.05:
            signals.append(TrendSignal(
                signal_type="draw_dying",
                direction="draw_dead",
                strength=0.9,
                description=(
                    f"Empate caiu de {draw_before:.0%} → {draw_now:.1%}. "
                    f"Com placar {latest.home_score}×{latest.away_score}, empate morreu."
                ),
                minute=latest.minute,
            ))

    return signals


# ──────────────────────────────────────────────────────────────────────────────
# Conselho de posição baseado em tendência
# ──────────────────────────────────────────────────────────────────────────────


def _user_bet_direction(picks: list[dict[str, Any]]) -> str:
    """Identifica a direção da aposta do usuário."""
    if not picks:
        return "unknown"
    pick = picks[0]
    market = pick.get("market", "")
    outcome = pick.get("outcome", "")

    if market == "h2h":
        if outcome in ("home", "1"):
            return "home_win"
        if outcome in ("away", "2"):
            return "away_win"
        if outcome in ("draw", "X"):
            return "draw"
    if market.startswith("totals"):
        if outcome == "over":
            return "over"
        return "under"
    if market == "btts":
        return "btts_yes" if outcome == "yes" else "btts_no"
    if market == "next_goal":
        if "home" in outcome:
            return "next_home"
        if "away" in outcome:
            return "next_away"
    return outcome or "unknown"


def _is_conflicting(bet_direction: str, signals: list[TrendSignal]) -> tuple[bool, str]:
    """Verifica se a aposta está contra a tendência do jogo."""
    conflicts = []

    for s in signals:
        # Apostou em empate mas empate está morrendo
        if bet_direction == "draw" and s.signal_type == "draw_dying":
            conflicts.append(s.description)
        if bet_direction == "draw" and s.signal_type == "score_gap":
            conflicts.append(s.description)

        # Apostou em vitória do visitante mas mandante domina
        if bet_direction == "away_win" and "home" in s.direction and s.strength > 0.6:
            conflicts.append(s.description)

        # Apostou em vitória do mandante mas visitante domina
        if bet_direction == "home_win" and "away" in s.direction and s.strength > 0.6:
            conflicts.append(s.description)

        # Apostou Under mas jogo está going Over
        if bet_direction == "under" and s.direction == "over":
            conflicts.append(s.description)

        # Apostou Over mas jogo travou (poucas oportunidades)
        if bet_direction == "over" and s.signal_type == "time_running_out":
            conflicts.append(s.description)

        # Apostou em próximo gol do visitante mas só mandante marca
        if bet_direction == "next_away" and s.direction == "home_only":
            conflicts.append(s.description)
        if bet_direction == "next_away" and s.direction == "home_certain":
            conflicts.append(s.description)

        # Apostou em próximo gol do mandante mas só visitante marca
        if bet_direction == "next_home" and s.direction == "away_only":
            conflicts.append(s.description)

        # Resultado locked = qualquer aposta contra é perdida
        if s.signal_type == "time_running_out" and s.strength > 0.7:
            if bet_direction in ("draw", "away_win") and "home" in str(signals):
                conflicts.append(s.description)
            if bet_direction in ("draw", "home_win") and "away" in str(signals):
                conflicts.append(s.description)

    is_conflict = len(conflicts) > 0
    reason = " | ".join(conflicts[:3]) if conflicts else ""
    return is_conflict, reason


def _find_best_opportunities(
    latest: GameTick, signals: list[TrendSignal]
) -> list[dict[str, Any]]:
    """Identifica as melhores oportunidades com base na tendência atual."""
    opps: list[dict[str, Any]] = []

    # Tendência Over com odd disponível?
    over_signals = [s for s in signals if s.direction == "over"]
    if over_signals:
        # Menor linha Over com implied > 60%
        for line, prob in sorted(latest.over_implied.items(), key=lambda x: float(x[0])):
            if prob > 0.55:
                fair_odd = 1 / prob if prob > 0 else 99
                opps.append({
                    "market": f"Over {line}",
                    "direction": "over",
                    "implied_prob": round(prob * 100, 1),
                    "fair_odd": round(fair_odd, 2),
                    "confidence": "alta" if prob > 0.70 else "média",
                    "reasoning": f"Jogo aberto — {latest.total_goals} gols já, tendência de mais.",
                })
                break  # só a melhor linha

    # Mandante dominando → vitória mandante (se odd > 1.01)
    home_dom_signals = [s for s in signals if "home" in s.direction and s.strength > 0.7]
    if home_dom_signals and latest.h2h_implied.get("1", 0) < 0.98:
        h2h_1_prob = latest.h2h_implied.get("1", 0)
        if h2h_1_prob > 0:
            opps.append({
                "market": "Resultado final (mandante)",
                "direction": "home_win",
                "implied_prob": round(h2h_1_prob * 100, 1),
                "fair_odd": round(1 / h2h_1_prob, 2) if h2h_1_prob > 0 else None,
                "confidence": "alta",
                "reasoning": "Mandante domina por placar e tendência — resultado praticamente certo.",
            })

    # Under — se jogo não está produzindo gols (sem goal_rush)
    goal_rush = any(s.signal_type == "goal_rush" for s in signals)
    if not goal_rush and latest.minute >= 60:
        remaining_min = 90 - latest.minute
        # Menor linha Under onde implied > 60%
        for line, over_prob in sorted(
            latest.over_implied.items(), key=lambda x: float(x[0])
        ):
            under_prob = 1 - over_prob
            if under_prob > 0.60:
                opps.append({
                    "market": f"Under {line}",
                    "direction": "under",
                    "implied_prob": round(under_prob * 100, 1),
                    "fair_odd": round(1 / under_prob, 2) if under_prob > 0 else None,
                    "confidence": "média",
                    "reasoning": (
                        f"Restam {remaining_min}min, ritmo sugere que não virão muitos gols."
                    ),
                })
                break

    return opps


def analyze_position(
    user_bet: dict[str, Any],
    ticks: list[GameTick],
    event_snapshot: dict[str, Any] | None = None,
) -> GameTrendReport:
    """Analisa a posição do usuário contra a tendência do jogo.

    Args:
        user_bet: aposta do usuário (com picks, stake, odds_placed, etc.)
        ticks: sequência cronológica de GameTick (mínimo 2 para detectar tendência)
        event_snapshot: snapshot raw mais recente (opcional, para contexto extra)

    Returns:
        GameTrendReport com sinais, tendência e conselho de ação.
    """
    if not ticks:
        return GameTrendReport()

    latest = ticks[-1]
    signals = detect_trends(ticks)

    # Direção da aposta do usuário
    picks = user_bet.get("picks") or []
    bet_direction = _user_bet_direction(picks)

    # Conflito entre aposta e tendência?
    is_conflict, conflict_reason = _is_conflicting(bet_direction, signals)

    # Calcular força agregada dos sinais conflitantes
    conflict_strength = max(
        (s.strength for s in signals if _signal_conflicts_with(s, bet_direction)), default=0
    )

    # Oportunidades alternativas
    opportunities = _find_best_opportunities(latest, signals)

    # ─── Decisão final ───
    if is_conflict and conflict_strength >= 0.8:
        advice = PositionAdvice(
            action="exit",
            urgency="critical",
            reasoning=(
                f"🚨 SAIA AGORA — Sua aposta ({bet_direction}) está diretamente contra "
                f"o fluxo do jogo. {conflict_reason}"
            ),
            confidence=conflict_strength,
        )
        # Sugerir reposicionamento
        if opportunities:
            best = opportunities[0]
            advice.reposition_to = best["market"]
            advice.reposition_detail = (
                f"{best['market']} — probabilidade {best['implied_prob']}%. "
                f"{best['reasoning']}"
            )
            advice.reposition_odd = best.get("fair_odd")

    elif is_conflict and conflict_strength >= 0.5:
        advice = PositionAdvice(
            action="exit",
            urgency="high",
            reasoning=(
                f"⚠️ Sua posição ({bet_direction}) está enfraquecendo. "
                f"Sinais contrários: {conflict_reason}. "
                f"Considere cash-out ou reposicionamento."
            ),
            confidence=conflict_strength,
        )
        if opportunities:
            best = opportunities[0]
            advice.reposition_to = best["market"]
            advice.reposition_detail = (
                f"Alternativa: {best['market']} — {best['reasoning']}"
            )
            advice.reposition_odd = best.get("fair_odd")

    elif is_conflict:
        advice = PositionAdvice(
            action="hold",
            urgency="medium",
            reasoning=(
                f"⏳ Atenção — há sinais iniciais contra sua posição ({bet_direction}). "
                f"Monitorar nos próximos minutos. Se piorar, sair."
            ),
            confidence=0.4,
        )

    else:
        # Sem conflito — aposta alinhada com tendência
        aligned_signals = [s for s in signals if _signal_aligns_with(s, bet_direction)]
        if aligned_signals:
            advice = PositionAdvice(
                action="hold",
                urgency="low",
                reasoning=(
                    f"✓ Sua posição ({bet_direction}) está ALINHADA com o jogo. "
                    f"Tendência favorável. Manter."
                ),
                confidence=max(s.strength for s in aligned_signals),
            )
        else:
            advice = PositionAdvice(
                action="hold",
                urgency="low",
                reasoning=(
                    "Sem sinais claros contra ou a favor. Jogo neutro para sua posição. Manter."
                ),
                confidence=0.3,
            )

    # Tendência dominante
    if signals:
        strongest = max(signals, key=lambda s: s.strength)
        dominant_trend = strongest.description
    else:
        dominant_trend = "Sem tendência clara"

    # Extrair info do evento
    home_team = ""
    away_team = ""
    event_id = 0
    if event_snapshot:
        home_team = event_snapshot.get("home_team", "")
        away_team = event_snapshot.get("away_team", "")
        event_id = event_snapshot.get("event_id", 0)

    return GameTrendReport(
        event_id=event_id,
        home_team=home_team,
        away_team=away_team,
        current_score=f"{latest.home_score}×{latest.away_score}",
        minute=latest.minute,
        signals=signals,
        dominant_trend=dominant_trend,
        position_advice=advice,
        best_opportunities=opportunities,
    )


def _signal_conflicts_with(signal: TrendSignal, bet_direction: str) -> bool:
    """Verifica se um sinal específico conflita com a direção da aposta."""
    conflicts_map = {
        "draw": ["score_gap", "draw_dying", "market_decided", "one_side_scoring"],
        "away_win": ["score_gap", "market_decided", "one_side_scoring", "time_running_out"],
        "home_win": ["score_gap", "market_decided", "one_side_scoring", "time_running_out"],
        "over": ["time_running_out"],
        "under": ["goal_rush", "over_trend"],
        "next_away": ["one_side_scoring", "market_decided"],
        "next_home": ["one_side_scoring", "market_decided"],
    }

    if bet_direction not in conflicts_map:
        return False

    if signal.signal_type not in conflicts_map[bet_direction]:
        return False

    # Verificar direção do sinal
    if bet_direction == "away_win" and "home" in signal.direction:
        return True
    if bet_direction == "home_win" and "away" in signal.direction:
        return True
    if bet_direction == "draw" and signal.signal_type in ("score_gap", "draw_dying"):
        return True
    if bet_direction == "under" and signal.direction == "over":
        return True
    if bet_direction == "over" and signal.signal_type == "time_running_out":
        return True
    if bet_direction == "next_away" and "home" in signal.direction:
        return True
    if bet_direction == "next_home" and "away" in signal.direction:
        return True
    if signal.signal_type == "market_decided":
        return True

    return False


def _signal_aligns_with(signal: TrendSignal, bet_direction: str) -> bool:
    """Verifica se um sinal suporta a direção da aposta."""
    if bet_direction == "home_win" and "home" in signal.direction:
        return True
    if bet_direction == "away_win" and "away" in signal.direction:
        return True
    if bet_direction == "over" and signal.direction == "over":
        return True
    if bet_direction == "under" and signal.signal_type == "time_running_out":
        return True
    if bet_direction == "next_home" and signal.direction == "home_only":
        return True
    if bet_direction == "next_away" and signal.direction == "away_only":
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Serialização para API
# ──────────────────────────────────────────────────────────────────────────────


def trend_report_to_dict(report: GameTrendReport) -> dict[str, Any]:
    """Converte GameTrendReport para JSON serializável."""
    return {
        "event_id": report.event_id,
        "home_team": report.home_team,
        "away_team": report.away_team,
        "current_score": report.current_score,
        "minute": report.minute,
        "dominant_trend": report.dominant_trend,
        "signals": [
            {
                "type": s.signal_type,
                "direction": s.direction,
                "strength": round(s.strength, 2),
                "description": s.description,
                "minute": s.minute,
            }
            for s in report.signals
        ],
        "position_advice": {
            "action": report.position_advice.action,
            "urgency": report.position_advice.urgency,
            "reasoning": report.position_advice.reasoning,
            "reposition_to": report.position_advice.reposition_to,
            "reposition_detail": report.position_advice.reposition_detail,
            "reposition_odd": report.position_advice.reposition_odd,
            "confidence": round(report.position_advice.confidence, 2),
        } if report.position_advice else None,
        "best_opportunities": report.best_opportunities,
    }
