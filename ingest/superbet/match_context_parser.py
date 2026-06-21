"""Parser de arquivos .txt/.md de análise pré-jogo.

Extrai métricas-chave para enriquecer o modelo ao vivo:
- Taxa de cartões do árbitro
- xG pré-jogo de cada time
- Times e informações do jogo
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class MatchContextData:
    home_team: str | None = None
    away_team: str | None = None
    referee_name: str | None = None
    referee_card_lambda: float | None = None  # média amarelos/jogo do árbitro
    referee_penalty_rate: float | None = None  # % jogos com pênalti
    home_pregame_xg: float | None = None
    away_pregame_xg: float | None = None
    home_avg_goals_scored: float | None = None
    away_avg_goals_scored: float | None = None
    h2h_avg_goals: float | None = None  # média gols por confronto direto
    raw_text: str = ""
    source_filename: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("raw_text")  # não persiste o texto completo no store
        return {k: v for k, v in d.items() if v is not None}


# ─── Padrões de extração ──────────────────────────────────────────────────────

_RE_TEAMS_HEADER = re.compile(
    r"(?:ANALISE|ANÁLISE|análise|analise)[^-\n]*[-–]\s*"
    r"([A-Za-zÀ-ÿ ]+)\s+[xX]\s+([A-Za-zÀ-ÿ ]+)",
    re.IGNORECASE,
)

_RE_TEAMS_VS = re.compile(
    r"([A-Za-zÀ-ÿ]{3,}(?:\s+[A-Za-zÀ-ÿ]+)?)\s+[xX]\s+([A-Za-zÀ-ÿ]{3,}(?:\s+[A-Za-zÀ-ÿ]+)?)",
)

_RE_REFEREE_BLOCK = re.compile(
    r"(?:ARBITRO|ÁRBITRO|árbitro|arbitro)[^\n]*\n(.*?)(?:\n={10,}|\Z)",
    re.DOTALL | re.IGNORECASE,
)

_RE_REFEREE_NAME = re.compile(
    r"(?:Nome completo|Árbitro|Arbitro)\s*[:\-]\s*([A-Za-zÀ-ÿ ]+)",
    re.IGNORECASE,
)

_RE_CARD_LAMBDA_SPECIFIC = re.compile(
    r"[Mm]edia\s+(?:de\s+)?(\d+[.,]\d+)\s+cartoes?\s+amarelos",
    re.IGNORECASE,
)

_RE_CARD_LAMBDA_CAREER = re.compile(
    r"Cartoes?\s+amarelos\s*[|\t]\s*[\d.,]+\s*[|\t]\s*(\d+[.,]\d+)",
    re.IGNORECASE,
)

_RE_PENALTY_RATE = re.compile(
    r"Penalt[ié]s?\s+marcados?\s*[|\t]\s*[\d.,]+\s*[|\t]\s*(\d+[.,]\d+)",
    re.IGNORECASE,
)

_RE_XG_HOME = re.compile(
    r"xG\s*\(gols?\s+esperados?\)\s*[|\t]\s*(\d+[.,]\d+)",
    re.IGNORECASE,
)

_RE_H2H_AVG_GOALS = re.compile(
    r"[Mm]edia\s+de\s+(\d+[.,]\d+)\s+gols?\s+por\s+(?:jogo|confronto)",
    re.IGNORECASE,
)

_RE_GOALS_BRAZIL = re.compile(
    r"Gols?\s+do\s+([A-Za-zÀ-ÿ]+)\s*:\s*(\d+)\s*\(media\s+de\s+(\d+[.,]\d+)",
    re.IGNORECASE,
)


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def parse_match_context(text: str, filename: str = "") -> MatchContextData:
    ctx = MatchContextData(raw_text=text, source_filename=filename)

    # Times
    m = _RE_TEAMS_HEADER.search(text)
    if m:
        ctx.home_team = m.group(1).strip().title()
        ctx.away_team = m.group(2).strip().title()

    # Árbitro: nome
    m = _RE_REFEREE_NAME.search(text)
    if m:
        ctx.referee_name = m.group(1).strip()

    # Taxa de cartões — prioriza a média mais específica encontrada no texto
    # (a que aparece mais alto e com mais contexto é a da liga principal)
    best_lambda: float | None = None
    for m in _RE_CARD_LAMBDA_SPECIFIC.finditer(text):
        val = _to_float(m.group(1))
        if best_lambda is None or val > best_lambda:
            best_lambda = val
    if best_lambda is None:
        m = _RE_CARD_LAMBDA_CAREER.search(text)
        if m:
            best_lambda = _to_float(m.group(1))
    ctx.referee_card_lambda = best_lambda

    # Pênalti rate (média de pênaltis por jogo)
    m = _RE_PENALTY_RATE.search(text)
    if m:
        ctx.referee_penalty_rate = _to_float(m.group(1))

    # xG dos times — pega os dois primeiros valores de xG encontrados em ordem
    xg_values = [_to_float(m.group(1)) for m in _RE_XG_HOME.finditer(text)]
    if len(xg_values) >= 1:
        ctx.home_pregame_xg = xg_values[0]
    if len(xg_values) >= 2:
        ctx.away_pregame_xg = xg_values[1]

    # Média de gols H2H
    m = _RE_H2H_AVG_GOALS.search(text)
    if m:
        ctx.h2h_avg_goals = _to_float(m.group(1))

    # Notas automáticas para exibição na UI
    notes: list[str] = []
    if ctx.referee_card_lambda:
        notes.append(
            f"Árbitro {ctx.referee_name or 'desconhecido'}: "
            f"{ctx.referee_card_lambda:.2f} amarelos/jogo (prior do modelo ajustado)"
        )
    if ctx.home_pregame_xg and ctx.away_pregame_xg:
        notes.append(
            f"xG pré-jogo: {ctx.home_team or 'Casa'} {ctx.home_pregame_xg:.2f} × "
            f"{ctx.away_pregame_xg:.2f} {ctx.away_team or 'Fora'}"
        )
    if ctx.h2h_avg_goals:
        notes.append(f"H2H: média de {ctx.h2h_avg_goals:.1f} gols/jogo no histórico")
    ctx.notes = notes

    return ctx
