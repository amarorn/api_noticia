"""
Overrides de probabilidade a partir da entrada dinâmica KXL (Fase 2).

Nota: com o motor de colisão (Fase 3), FECL/FEJU/FEDE/FEPT/FEEM são aplicados
em pipelines/wc_kxl_collision.py. Este módulo permanece para testes e uso avulso.
"""

from __future__ import annotations

from dataclasses import dataclass

from schemas.wc_kxl_dynamic import (
    FedeDesfalque,
    FeptJogador,
    WcKxlMatchInput,
)

ATTACK_LINES = frozenset({"ataque", "atacante", "forward", "fw", "w", "st"})
DEFENSE_LINES = frozenset({"defesa", "defensor", "defender", "df", "cb", "lb", "rb", "gk", "goleiro"})
WET_PITCH = frozenset({"molhado", "ruim", "encharcado", "pesado"})


@dataclass(frozen=True)
class DynamicOverrideResult:
    prob_home: float
    prob_draw: float
    prob_away: float
    deltas: dict[str, float]
    notes: list[str]


def _squad_penalty(desfalques: list[FedeDesfalque]) -> float:
    total = 0.0
    for d in desfalques:
        if d.impacto is not None:
            total += d.impacto
        elif d.nota_elenco is not None:
            total += min(0.12, d.nota_elenco / 100.0 + 0.04)
        else:
            total += 0.03
    return min(total, 0.25)


def _line_bucket(player: FeptJogador) -> str | None:
    if player.linha:
        key = player.linha.strip().lower()
        if key in ATTACK_LINES:
            return "attack"
        if key in DEFENSE_LINES:
            return "defense"
    pos = (player.posicao or "").strip().lower()
    if pos in {"gk", "gol", "goleiro"} or pos.startswith("d"):
        return "defense"
    if pos.startswith(("f", "w", "s")) or pos in {"st", "cf"}:
        return "attack"
    return None


def _avg_rating(players: list[FeptJogador], bucket: str) -> float | None:
    ratings: list[float] = []
    for p in players:
        if p.nota_sofascore is None:
            continue
        b = _line_bucket(p)
        if b == bucket:
            ratings.append(p.nota_sofascore)
    if not ratings:
        return None
    return sum(ratings) / len(ratings)


def _referee_punitivist(feju) -> float:
    if feju.perfil:
        p = feju.perfil.strip().lower()
        if p == "punitivista":
            return 0.85
        if p == "pacificador":
            return 0.15
        if p == "equilibrado":
            return 0.5
    score = 0.5
    if feju.indice_cartao_falta is not None:
        score = min(1.0, feju.indice_cartao_falta / 0.35)
    if feju.cartoes_media is not None:
        score = max(score, min(1.0, (feju.cartoes_media - 3.0) / 5.0))
    if feju.faltas_media is not None:
        score = max(score, min(1.0, (feju.faltas_media - 22.0) / 18.0))
    return score


def _apply_fecl(fecl, d_home: float, d_draw: float, d_away: float, notes: list[str]):
    wet = False
    if fecl.chuva_mm is not None and fecl.chuva_mm >= 3.0:
        wet = True
    if fecl.umidade_pct is not None and fecl.umidade_pct >= 85.0:
        wet = True
    if fecl.gramado and fecl.gramado.strip().lower() in WET_PITCH:
        wet = True
    if wet:
        d_draw += 0.045
        d_home -= 0.022
        d_away -= 0.022
        notes.append("Clima/gramado adversos: mais empate e menos ritmo ofensivo")
    if fecl.altitude_m is not None and fecl.altitude_m >= 1500.0:
        d_draw += 0.015
        notes.append("Altitude elevada: leve favorecimento ao empate")
    return d_home, d_draw, d_away


def _apply_feju(feju, d_home: float, d_draw: float, d_away: float, notes: list[str]):
    pun = _referee_punitivist(feju)
    if pun >= 0.65:
        d_draw += 0.03 * pun
        d_home -= 0.015 * pun
        d_away -= 0.015 * pun
        notes.append("Árbitro punitivista: mais paradas e cenário de empate")
    elif pun <= 0.35:
        d_draw -= 0.01
        notes.append("Árbitro permissivo: jogo mais fluido")
    return d_home, d_draw, d_away


def _apply_fede(fede, d_home: float, d_draw: float, d_away: float, notes: list[str]):
    pen_h = _squad_penalty(fede.desfalques_mandante)
    pen_a = _squad_penalty(fede.desfalques_visitante)
    if pen_h > 0:
        d_home -= pen_h
        d_draw += pen_h * 0.45
        d_away += pen_h * 0.55
        notes.append(f"Desfalques mandante (−{pen_h:.0%} força)")
    if pen_a > 0:
        d_away -= pen_a
        d_draw += pen_a * 0.45
        d_home += pen_a * 0.55
        notes.append(f"Desfalques visitante (−{pen_a:.0%} força)")
    return d_home, d_draw, d_away


def _apply_fept(fept, d_home: float, d_draw: float, d_away: float, notes: list[str]):
    home_atk = _avg_rating(fept.titulares_mandante, "attack")
    away_def = _avg_rating(fept.titulares_visitante, "defense")
    away_atk = _avg_rating(fept.titulares_visitante, "attack")
    home_def = _avg_rating(fept.titulares_mandante, "defense")

    if home_atk is not None and away_def is not None:
        gap = home_atk - away_def
        if gap >= 0.8:
            boost = min(0.06, (gap - 0.8) * 0.04 + 0.03)
            d_home += boost
            d_away -= boost * 0.6
            notes.append(
                f"Nota atacantes mandante vs defesa visitante (+{gap:.1f}): pressão no 1"
            )
        elif gap <= -0.5:
            d_home -= 0.02
            d_away += 0.02

    if away_atk is not None and home_def is not None:
        gap = away_atk - home_def
        if gap >= 0.8:
            boost = min(0.06, (gap - 0.8) * 0.04 + 0.03)
            d_away += boost
            d_home -= boost * 0.6
            notes.append(
                f"Nota atacantes visitante vs defesa mandante (+{gap:.1f}): pressão no 2"
            )
    return d_home, d_draw, d_away


def _apply_feem(feem, d_home: float, d_draw: float, d_away: float, notes: list[str]):
    chaos = feem.contexto_caos_extra + feem.peso_rivalidade * 0.5
    if feem.jogo_decisivo:
        chaos += 0.15
    if chaos > 0:
        d_draw += min(0.05, chaos * 0.04)
        shrink = min(0.03, chaos * 0.02)
        d_home -= shrink
        d_away -= shrink
        notes.append("Contexto emocional/caótico: maior chance de empate")
    return d_home, d_draw, d_away


def apply_dynamic_overrides(
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    match_input: WcKxlMatchInput | None,
) -> DynamicOverrideResult:
    if match_input is None:
        return DynamicOverrideResult(
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            deltas={},
            notes=[],
        )

    d_home = d_draw = d_away = 0.0
    notes: list[str] = []

    if match_input.fecl:
        d_home, d_draw, d_away = _apply_fecl(
            match_input.fecl, d_home, d_draw, d_away, notes
        )
    if match_input.feju:
        d_home, d_draw, d_away = _apply_feju(
            match_input.feju, d_home, d_draw, d_away, notes
        )
    if match_input.fede:
        d_home, d_draw, d_away = _apply_fede(
            match_input.fede, d_home, d_draw, d_away, notes
        )
    if match_input.fept:
        d_home, d_draw, d_away = _apply_fept(
            match_input.fept, d_home, d_draw, d_away, notes
        )
    if match_input.feem:
        d_home, d_draw, d_away = _apply_feem(
            match_input.feem, d_home, d_draw, d_away, notes
        )

    ph = max(0.01, prob_home + d_home)
    pd = max(0.01, prob_draw + d_draw)
    pa = max(0.01, prob_away + d_away)
    total = ph + pd + pa

    return DynamicOverrideResult(
        prob_home=ph / total,
        prob_draw=pd / total,
        prob_away=pa / total,
        deltas={"home": d_home, "draw": d_draw, "away": d_away},
        notes=notes,
    )


def format_dynamic_context(result: DynamicOverrideResult) -> str:
    if not result.notes:
        return ""
    lines = ["## Ajustes do dia (KXL dinâmico)", ""]
    for note in result.notes:
        lines.append(f"- {note}")
    if result.deltas:
        lines.append(
            f"- Deltas aplicados: mandante {result.deltas.get('home', 0):+.3f}, "
            f"empate {result.deltas.get('draw', 0):+.3f}, "
            f"visitante {result.deltas.get('away', 0):+.3f}"
        )
    return "\n".join(lines)
