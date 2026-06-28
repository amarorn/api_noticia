"""KXL dinâmico ao vivo: Kelly fraction e blend de baseline adaptados ao estado do jogo.

Substitui as constantes estáticas:
  - `kxl_blend_weight = 0.20` → varia com minuto, confiança e n_eventos
  - `kelly_quarter = kelly * 0.25` → divisor dinâmico por confiança/minuto

Princípio:
  - Início do jogo: blend alto (confia mais nos baselines KXL)
    → pouca informação ao vivo, baselines históricos valem mais
  - Durante o jogo: blend cai conforme eventos acumulam e modelo ganha confiança
  - Kelly: divisor aumenta (mais conservador) quando confiança é baixa ou odds volatilizam

Uso:
    from models.wc_kelly_live import compute_live_kxl_weight, compute_live_kelly

    kxl = compute_live_kxl_weight(minute=65, confidence_score=0.72, n_live_events=8)
    stake_pct = compute_live_kelly(ev=0.12, odds=2.10, model_prob=0.55, minute=65, confidence_score=0.72)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import settings


# ---------------------------------------------------------------------------
# Parâmetros do KXL dinâmico
# ---------------------------------------------------------------------------

_KXL_BASE = 0.20          # blend base (estático) — calibrado em 2022
_KXL_EARLY_BONUS = 0.15   # bonus adicional no início (min 0 → blend 0.35)
_KXL_EVENT_DECAY = 0.10   # redução máxima por n_eventos (20+ eventos → -0.10)
_KXL_CONF_DECAY = 0.10    # redução adicional se confiança alta (model > market)
_KXL_MIN = 0.05
_KXL_MAX = 0.40

# Kelly dinâmico
_KELLY_BASE_DIVISOR = 4.0   # quarter-Kelly padrão
_KELLY_MAX_DIVISOR = 8.0    # muito conservador (confiança baixa)
_KELLY_MIN_DIVISOR = 2.5    # semi-Kelly (confiança alta, jogo avançado)


# ---------------------------------------------------------------------------
# KXL blend dinâmico
# ---------------------------------------------------------------------------

def compute_live_kxl_weight(
    minute: float,
    confidence_score: float = 0.5,
    n_live_events: int = 0,
) -> float:
    """Calcula peso KXL (blend baseline/modelo) adaptado ao estado do jogo.

    Quanto maior o retorno, mais peso para os baselines históricos.
    Quanto menor, mais peso para o modelo in-play.

    Args:
        minute: minuto atual (0–90+).
        confidence_score: score de confiança do ensemble (0–1).
        n_live_events: número de eventos Sofascore coletados (goals, cards, subs).

    Returns:
        Peso KXL em [_KXL_MIN, _KXL_MAX].
    """
    # Bonus inicial: nos primeiros 15 min, baselines são mais confiáveis
    minute_fraction = min(minute, 90.0) / 90.0
    early_bonus = _KXL_EARLY_BONUS * max(0.0, 1.0 - minute_fraction * 3)  # linear até 30'

    # Decaimento por eventos ao vivo
    n_capped = min(n_live_events, 20)
    events_decay = _KXL_EVENT_DECAY * (n_capped / 20.0)

    # Decaimento por confiança do modelo (confiança alta → modelo domina)
    conf_decay = _KXL_CONF_DECAY * max(0.0, confidence_score - 0.5) * 2.0  # ativo acima de 0.5

    weight = _KXL_BASE + early_bonus - events_decay - conf_decay
    return float(np.clip(weight, _KXL_MIN, _KXL_MAX))


# ---------------------------------------------------------------------------
# Kelly live dinâmico
# ---------------------------------------------------------------------------

def compute_live_kelly(
    ev: float,
    odds: float,
    model_prob: float,
    minute: float,
    confidence_score: float = 0.5,
    bankroll: float = 1000.0,
    max_stake_pct: float | None = None,
) -> "LiveKellyResult":
    """Calcula stake recomendado com Kelly dinâmico adaptado ao jogo ao vivo.

    Ajusta o divisor do Kelly com base em:
    - Minuto avançado + confiança alta → divisor menor (mais agressivo)
    - Início do jogo ou baixa confiança → divisor maior (mais conservador)

    Args:
        ev: expected value (ex: 0.12 = +12%).
        odds: odds decimais.
        model_prob: probabilidade do modelo.
        minute: minuto atual.
        confidence_score: confiança do ensemble (0–1).
        bankroll: banca em R$.
        max_stake_pct: limite máximo como % da banca.

    Returns:
        LiveKellyResult com stake_pct, stake_brl e metadata.
    """
    if odds <= 1.0 or model_prob <= 0:
        return LiveKellyResult(
            full_kelly=0.0, divisor=_KELLY_BASE_DIVISOR,
            fraction=0.0, stake_pct=0.0, stake_brl=0.0,
            minute=minute, confidence_score=confidence_score,
        )

    # Kelly full
    full_kelly = max(0.0, (model_prob * odds - 1.0) / (odds - 1.0))

    # Divisor dinâmico
    minute_fraction = min(minute, 90.0) / 90.0
    # Tarde no jogo + boa confiança → mais agressivo
    aggression = minute_fraction * confidence_score  # 0→0, 1→conf

    # Interpolar entre MAX e MIN divisor
    divisor = _KELLY_MAX_DIVISOR - aggression * (_KELLY_MAX_DIVISOR - _KELLY_MIN_DIVISOR)
    divisor = float(np.clip(divisor, _KELLY_MIN_DIVISOR, _KELLY_MAX_DIVISOR))

    fraction = full_kelly / divisor if divisor > 0 else 0.0

    # Cap por configuração
    max_pct = max_stake_pct or getattr(settings, "bet_max_stake_pct", 5.0)
    stake_pct = float(np.clip(fraction * 100, 0.0, max_pct))
    stake_brl = round(bankroll * stake_pct / 100, 2)

    return LiveKellyResult(
        full_kelly=round(full_kelly, 4),
        divisor=round(divisor, 2),
        fraction=round(fraction, 4),
        stake_pct=round(stake_pct, 2),
        stake_brl=stake_brl,
        minute=minute,
        confidence_score=confidence_score,
    )


@dataclass
class LiveKellyResult:
    """Resultado do Kelly live dinâmico."""

    full_kelly: float       # Kelly fraction completa
    divisor: float          # divisor dinâmico usado
    fraction: float         # full_kelly / divisor
    stake_pct: float        # % da banca recomendada
    stake_brl: float        # valor em R$
    minute: float
    confidence_score: float

    def to_dict(self) -> dict[str, float]:
        return {
            "full_kelly": self.full_kelly,
            "kelly_divisor": self.divisor,
            "kelly_fraction": self.fraction,
            "stake_pct": self.stake_pct,
            "stake_brl": self.stake_brl,
            "minute": self.minute,
            "confidence_score": self.confidence_score,
        }


# ---------------------------------------------------------------------------
# Integração: atualiza o odds opportunity com kelly dinâmico
# ---------------------------------------------------------------------------

def enrich_opportunity_with_live_kelly(
    opportunity: dict,
    minute: float,
    confidence_score: float,
    bankroll: float = 1000.0,
) -> dict:
    """Adiciona stake dinâmico a um dict de opportunity retornado pelo advice.

    Substitui ou complementa kelly_quarter e suggested_stake com valores
    dinâmicos adaptados ao momento do jogo.

    Args:
        opportunity: dict com 'ev', 'odds', 'model_prob' etc.
        minute: minuto atual.
        confidence_score: confiança do ensemble.
        bankroll: banca em R$.

    Returns:
        Cópia do dict com chaves 'live_kelly_*' adicionadas.
    """
    ev = float(opportunity.get("ev") or 0)
    odds = float(opportunity.get("odds") or 1.5)
    model_prob = float(opportunity.get("model_prob") or 0.5)

    result = compute_live_kelly(
        ev=ev,
        odds=odds,
        model_prob=model_prob,
        minute=minute,
        confidence_score=confidence_score,
        bankroll=bankroll,
    )

    return {
        **opportunity,
        "live_kelly_full": result.full_kelly,
        "live_kelly_divisor": result.divisor,
        "live_kelly_fraction": result.fraction,
        "live_stake_pct": result.stake_pct,
        "live_stake_brl": result.stake_brl,
    }
