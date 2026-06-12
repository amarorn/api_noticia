"""Timing e fundamentação de apostas in-play baseados em probabilidade do modelo.

Prioridade: edge probabilístico (modelo vs mercado) e histórico de ticks —
não EV alto por odd inflada.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import settings
from models.wc_trend_advisor import GameTick, load_event_ticks


def _implied_from_tick(tick: GameTick, market: str, outcome: str) -> float | None:
    """Probabilidade implícita do mercado num tick anterior."""
    out = outcome.upper()
    if market == "h2h":
        key = "X" if out in {"X", "0", "DRAW"} else out
        return tick.h2h_implied.get(key)
    if market.startswith("over_") or market.endswith("_over_*"):
        pass
    if market.startswith(("over_", "1h_over_", "2h_over_")) and out in {"yes", "sim"}:
        line = market.split("_over_", 1)[-1].replace("_", ".")
        return tick.over_implied.get(line)
    if market == "btts" and out in {"YES", "SIM"}:
        return None
    if market == "next_goal":
        if out == "HOME":
            odd = tick.next_goal_home_odd
            return 1.0 / odd if odd and odd > 1 else None
        if out == "AWAY":
            odd = tick.next_goal_away_odd
            return 1.0 / odd if odd and odd > 1 else None
    return None


def assess_bet_timing(
    *,
    event_id: int | None,
    market: str,
    outcome: str,
    model_prob: float,
    implied_prob: float,
) -> dict[str, str]:
    """Detecta se é momento de entrar com base na evolução da linha."""
    edge_pp = (model_prob - implied_prob) * 100
    min_pp = settings.live_min_edge_pp

    if edge_pp < min_pp:
        return {
            "timing": "aguardar",
            "timing_reason": (
                f"Edge probabilístico de {edge_pp:.1f} pp — abaixo do mínimo de {min_pp:.0f} pp "
                f"exigido pelo modelo. Sem fundamento estatístico para apostar agora."
            ),
        }

    timing = "monitorar"
    reason = (
        f"Modelo {model_prob:.0%} vs mercado {implied_prob:.0%} (+{edge_pp:.1f} pp). "
        f"Acompanhe os próximos refreshes (~25s) para confirmar se a linha mantém valor."
    )

    if event_id is None:
        return {"timing": timing, "timing_reason": reason}

    event_dir = Path(settings.lake_root) / "bronze" / "superbet" / "events" / str(event_id)
    ticks = load_event_ticks(event_dir)
    if len(ticks) < 2:
        return {"timing": timing, "timing_reason": reason}

    prev_implied = _implied_from_tick(ticks[-2], market, outcome)
    if prev_implied is None:
        return {"timing": timing, "timing_reason": reason}

    delta_pp = (implied_prob - prev_implied) * 100
    if delta_pp <= -1.5:
        return {
            "timing": "agora",
            "timing_reason": (
                f"A casa reduziu a probabilidade implícita em {abs(delta_pp):.1f} pp desde o "
                f"último refresh — a odd subiu enquanto o modelo mantém {model_prob:.0%} "
                f"(edge +{edge_pp:.1f} pp). Janela favorável para entrar."
            ),
        }
    if delta_pp >= 1.5:
        return {
            "timing": "aguardar",
            "timing_reason": (
                f"A linha enxugou {delta_pp:.1f} pp desde o último tick — o mercado está "
                f"corrigindo. Aguarde a odd voltar a favorecer o modelo antes de apostar."
            ),
        }

    return {"timing": timing, "timing_reason": reason}


def build_fundamentacao(
    *,
    confidence: dict[str, Any] | None,
    market: str,
    model_prob: float,
    implied_prob: float,
    edge_pp: float,
    minute: int,
) -> str:
    """Explicação ancorada no modelo — nunca achismo."""
    parts: list[str] = []

    if confidence:
        label = confidence.get("label", "")
        score = float(confidence.get("score") or 0)
        if label == "especulativa" or score < 0.25:
            parts.append(
                "⚠️ Dados históricos insuficientes para estes times — previsão baseada em "
                "médias genéricas do ensemble (Poisson + GBM quando disponível)."
            )
        elif label == "baixa" or score < 0.5:
            parts.append(
                f"Confiança {label} ({score:.0%}): amostra limitada — exigimos edge maior "
                f"para recomendar."
            )
        else:
            parts.append(
                f"Confiança {label} ({score:.0%}): previsão ancorada em Elo, forma, xG Sofascore "
                f"e simulação Monte Carlo in-play (min {minute}')."
            )
        conf_reason = confidence.get("reason")
        if conf_reason and score >= 0.5:
            parts.append(str(conf_reason))
    else:
        parts.append(
            "Estimativa via simulação Poisson in-play condicionada ao placar e minuto, "
            "blend com mercado quando disponível."
        )

    parts.append(
        f"Probabilidade real estimada: {model_prob:.0%}. "
        f"Mercado precifica como {implied_prob:.0%}. "
        f"Vantagem do modelo: +{edge_pp:.1f} pontos percentuais."
    )

    if market.startswith("2h_"):
        parts.append("Mercado do 2º tempo — λ calibrado no pré-jogo + estado atual do placar.")
    elif market.startswith("1h_"):
        parts.append("Mercado do 1º tempo — condicionado ao ritmo observado até agora.")
    elif market.startswith("over_") or "over" in market:
        parts.append("Total de gols — distribuição Poisson bivariada com correlação Dixon-Coles.")

    return " ".join(parts)
