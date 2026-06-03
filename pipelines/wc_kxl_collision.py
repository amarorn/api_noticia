"""
Motor KXL — Método de Colisão (Energia × Espaço × Tempo).

Ver docs/kxl-colisao.md para derivação e limitações.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pipelines.wc_baselines import load_team_baselines, resolve_baseline_team
from pipelines.wc_kxl_fept import (
    fecl_is_synthetic,
    fecl_is_wet,
    fept_esquema,
    fept_players_for_side,
    scheme_modifiers,
    weighted_squad_energy,
)
from schemas.wc_kxl_dynamic import (
    FedeDesfalque,
    FeptJogador,
    WcKxlMatchInput,
)

SECTORS = (
    ("direita", "EADR_dir", "EGFD_sofrido_dir"),
    ("esquerda", "EAES_esq", "EGFE_sofrido_esq"),
    ("meio", "EAME_meio", "EGFM_sofrido_meio"),
)
TBRTL_REF_SEC = 1800.0
WET_PITCH = frozenset({"molhado", "ruim", "encharcado", "pesado"})
ATTACK_LINES = frozenset({"ataque", "atacante", "forward", "fw", "w", "st"})
DEFENSE_LINES = frozenset({"defesa", "defensor", "defender", "df", "cb", "lb", "rb", "gk", "goleiro"})


@dataclass(frozen=True)
class SectorCollision:
    label: str
    attack_dna: float
    defense_permissivity: float
    inside_lethality: float
    gk_inside_weakness: float
    score: float


@dataclass(frozen=True)
class LethalityGkCell:
    method: str
    attack_pct: float
    gk_weak_pct: float
    pressure: float


@dataclass(frozen=True)
class LethalityGkMatrix:
    cells: tuple[LethalityGkCell, ...]
    dominant: str
    index: float
    eacp: float


@dataclass(frozen=True)
class TeamCollisionVectors:
    team: str
    energia: float
    espaco: float
    tempo: float
    vcar_raw: float
    vesc: float
    v_eff: float
    sectors: tuple[SectorCollision, ...]
    lethality: LethalityGkMatrix
    modulators: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CollisionPredictResult:
    prob_home: float
    prob_draw: float
    prob_away: float
    home: TeamCollisionVectors
    away: TeamCollisionVectors
    sector_note: str
    lethality_note: str
    v_delta: float
    notes: list[str]


LETALITY_METHODS = (
    ("cabeça", "EAGC_cabeca", "EGCF_sofrido_cabeca"),
    ("fora da área", "EAGF_fora", "EGSF_sofrido_fora"),
    ("dentro da área", "EAGD_dentro", "EGSD_sofrido_dentro"),
    ("bola parada", "EABP_parada", None),
)


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _baseline_entry(team: str) -> dict | None:
    return load_team_baselines().get(resolve_baseline_team(team))


def _ecpe_from_entry(entry: dict) -> float:
    ec = (entry.get("baseline_eixos") or {}).get("conectividade_ec") or {}
    return _num(ec.get("ECPE_passes_errados_pct"), 15.0)


def _energy_from_baseline(entry: dict) -> float:
    ea = (entry.get("baseline_eixos") or {}).get("ataque_ea") or {}
    ec = (entry.get("baseline_eixos") or {}).get("conectividade_ec") or {}
    letal = ea.get("letalidade_metodo") or {}
    volume = ea.get("volume") or {}
    ecdc = _num(ec.get("ECDC_dribles_jogo"), 8.0)
    eagd = _num(letal.get("EAGD_dentro"), 45.0)
    ecch = _num(volume.get("ECCH_chutes_totais"), 14.0)
    ecpe = _ecpe_from_entry(entry)
    ecpe_penalty = min(0.08, max(0.0, (ecpe - 14.0) / 100.0))
    base = 0.32 * (ecdc / 12.0) + 0.32 * (eagd / 55.0) + 0.28 * (ecch / 18.0)
    return max(0.5, base - ecpe_penalty)


def _energy_from_fept(players: list[FeptJogador]) -> float | None:
    ratings: list[float] = []
    for p in players:
        if p.nota_sofascore is None:
            continue
        if _line_bucket(p) == "attack":
            ratings.append(p.nota_sofascore)
    if not ratings:
        return None
    return _clamp(sum(ratings) / len(ratings) / 7.5, 0.5, 1.3)


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


def _avg_line_rating(players: list[FeptJogador], bucket: str) -> float | None:
    vals = [p.nota_sofascore for p in players if p.nota_sofascore is not None and _line_bucket(p) == bucket]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _eacp_from_entry(entry: dict) -> float:
    ea = (entry.get("baseline_eixos") or {}).get("ataque_ea") or {}
    return _num((ea.get("volume") or {}).get("EACP_chances_perdidas"), 1.5)


def _lethality_gk_matrix(attack_entry: dict, defense_entry: dict) -> LethalityGkMatrix:
    ea = (attack_entry.get("baseline_eixos") or {}).get("ataque_ea") or {}
    eg = (defense_entry.get("baseline_eixos") or {}).get("goleiro_baliza_eg") or {}
    letal = ea.get("letalidade_metodo") or {}
    gk_weak = eg.get("fraquezas") or {}
    eacp = _eacp_from_entry(attack_entry)

    cells: list[LethalityGkCell] = []
    for method, atk_key, gk_key in LETALITY_METHODS:
        atk_pct = _num(letal.get(atk_key), 15.0)
        if gk_key:
            gk_pct = _num(gk_weak.get(gk_key), 50.0)
        else:
            gk_pct = (
                _num(gk_weak.get("EGCF_sofrido_cabeca"), 15.0)
                + _num(gk_weak.get("EGSF_sofrido_fora"), 15.0)
                + _num(gk_weak.get("EGSD_sofrido_dentro"), 70.0)
            ) / 3.0
        pressure = (atk_pct / 55.0) * (gk_pct / 100.0)
        cells.append(
            LethalityGkCell(
                method=method,
                attack_pct=round(atk_pct, 1),
                gk_weak_pct=round(gk_pct, 1),
                pressure=round(pressure, 4),
            )
        )

    dominant = max(cells, key=lambda c: c.pressure).method
    index = _clamp(max(c.pressure for c in cells) * 2.2, 0.0, 1.0)
    return LethalityGkMatrix(
        cells=tuple(cells),
        dominant=dominant,
        index=round(index, 4),
        eacp=round(eacp, 2),
    )


def _sector_collisions(attack_entry: dict, defense_entry: dict) -> tuple[SectorCollision, ...]:
    ea = (attack_entry.get("baseline_eixos") or {}).get("ataque_ea") or {}
    ed = (defense_entry.get("baseline_eixos") or {}).get("defensivo_ed") or {}
    eg = (defense_entry.get("baseline_eixos") or {}).get("goleiro_baliza_eg") or {}
    dna = ea.get("DNA_direcional") or {}
    letal = ea.get("letalidade_metodo") or {}
    perm = ed.get("permissividade_setor") or {}
    gk_weak = eg.get("fraquezas") or {}
    inside = _num(letal.get("EAGD_dentro"), 45.0)
    eg_sd = _num(gk_weak.get("EGSD_sofrido_dentro"), 70.0)
    out: list[SectorCollision] = []
    for label, atk_k, perm_k in SECTORS:
        atk = _num(dna.get(atk_k))
        weakness = _num(perm.get(perm_k), 0.3)
        score = atk * weakness * (1.0 + (inside / 100.0) * (eg_sd / 100.0))
        out.append(
            SectorCollision(
                label=label,
                attack_dna=atk,
                defense_permissivity=weakness,
                inside_lethality=inside,
                gk_inside_weakness=eg_sd,
                score=round(score, 4),
            )
        )
    return tuple(out)


def _tempo_factor(entry: dict) -> float:
    ttbp = _num((entry.get("historico_atrito_temporal") or {}).get("TTBP_provocado_segundos"), 1650.0)
    return _clamp(ttbp / TBRTL_REF_SEC, 0.7, 1.15)


def _vesc_from_entry(entry: dict, mod_esc: float = 1.0) -> float:
    ed = (entry.get("baseline_eixos") or {}).get("defensivo_ed") or {}
    eg = (entry.get("baseline_eixos") or {}).get("goleiro_baliza_eg") or {}
    gk_weak = eg.get("fraquezas") or {}
    eddf = _num(ed.get("EDDF_desarmes_cortes"), 20.0)
    edct = _num(ed.get("EDCT_chutes_sofridos"), 10.0)
    eg_sd = _num(gk_weak.get("EGSD_sofrido_dentro"), 70.0)
    egbs = _num(eg.get("EGBS_bolas_espalmadas"), 20.0)
    gk = (100.0 - eg_sd) / 100.0
    reflex = min(1.0, egbs / 28.0) * 0.08
    base = 0.38 * (eddf / 26.0) + 0.33 * ((12.0 - min(edct, 12.0)) / 12.0) + 0.21 * gk + reflex
    return base * mod_esc


def _squad_penalty(desfalques: list[FedeDesfalque]) -> float:
    total = 0.0
    for d in desfalques:
        if d.impacto_nota_elenco is not None:
            total += min(0.15, abs(d.impacto_nota_elenco) / 5.0)
        elif d.impacto is not None:
            total += d.impacto
        elif d.nota_elenco is not None:
            total += min(0.12, d.nota_elenco / 100.0 + 0.04)
        else:
            total += 0.03
    return min(total, 0.25)


def _referee_profile(feju) -> str:
    if feju.perfil:
        return feju.perfil.strip().lower()
    if feju.indice_cartao_falta is not None and feju.indice_cartao_falta >= 0.28:
        return "punitivista"
    if feju.cartoes_media is not None and feju.cartoes_media >= 5.0:
        return "punitivista"
    if feju.cartoes_media is not None and feju.cartoes_media <= 3.5:
        return "pacificador"
    return "equilibrado"


def _build_modulators(
    side: str,
    kxl: WcKxlMatchInput | None,
    is_home: bool,
) -> tuple[dict[str, float], list[str]]:
    """Moduladores M no Vcar/Vesc (regras PDF + Fase 2)."""
    m: dict[str, float] = {"vcar": 1.0, "vesc": 1.0, "ecpc": 1.0, "draw_bias": 0.0, "atrito": 0.0}
    notes: list[str] = []
    if kxl is None:
        return m, notes

    if kxl.fecl:
        if fecl_is_wet(kxl.fecl):
            m["ecpc"] = 0.90
            m["vesc"] = 1.12
            m["draw_bias"] += 0.04
            notes.append("FECL: chuva/umidade — ECPC−10%, Vesc+12% (PDF)")
        if fecl_is_synthetic(kxl.fecl):
            m["vcar"] *= 1.03
            notes.append("FECL: gramado sintético — ritmo ligeiramente maior")
        if kxl.fecl.temperatura_c is not None and kxl.fecl.temperatura_c >= 32.0:
            m["draw_bias"] += 0.02
            notes.append("FECL: calor extremo — mais empate")

    if kxl.fept:
        esquema = fept_esquema(kxl.fept, is_home)
        vcar_m, vesc_m, note = scheme_modifiers(esquema)
        if note:
            m["vcar"] *= vcar_m
            m["vesc"] *= vesc_m
            notes.append(f"FEPT: {note}")

    if kxl.feju:
        perfil = _referee_profile(kxl.feju)
        if perfil == "punitivista":
            m["vcar"] = 1.25
            m["draw_bias"] += 0.03
            notes.append("FEJU: árbitro punitivista — Vcar×1.25 (PDF)")
        elif perfil == "pacificador":
            m["vcar"] = 0.85
            notes.append("FEJU: árbitro pacificador — Vcar×0.85 (PDF)")

    if kxl.fede:
        desfalques = (
            kxl.fede.desfalques_mandante if is_home else kxl.fede.desfalques_visitante
        )
        pen = _squad_penalty(desfalques)
        if pen > 0:
            m["vcar"] *= max(0.6, 1.0 - pen)
            notes.append(f"FEDE: desfalques {side} — Vcar×{m['vcar']:.2f}")

    if kxl.feem:
        chaos = kxl.feem.contexto_caos_extra + kxl.feem.peso_rivalidade * 0.5
        if kxl.feem.contexto_peso_caos is not None:
            chaos += max(0.0, kxl.feem.contexto_peso_caos - 1.0)
        if kxl.feem.jogo_decisivo:
            chaos += 0.15
        if chaos > 0:
            m["draw_bias"] += min(0.05, chaos * 0.04)
            notes.append("FEEM: contexto caótico — mais empate")

    return m, notes


def _team_vectors(
    team: str,
    entry: dict,
    opponent_entry: dict,
    opponent_vesc: float,
    kxl: WcKxlMatchInput | None,
    is_home: bool,
) -> TeamCollisionVectors:
    sectors = _sector_collisions(entry, opponent_entry)
    lethality = _lethality_gk_matrix(entry, opponent_entry)
    espaco = sum(s.score for s in sectors) / max(len(sectors), 1)

    energia = _energy_from_baseline(entry)
    if kxl and kxl.fept:
        players = fept_players_for_side(kxl.fept, is_home)
        e_live = weighted_squad_energy(players) or _energy_from_fept(players)
        if e_live is not None:
            energia = e_live

    tempo = _tempo_factor(entry)
    fsc = _num((entry.get("historico_atrito_temporal") or {}).get("FSC_fator_caos_base"), 1.0)
    ea = (entry.get("baseline_eixos") or {}).get("ataque_ea") or {}
    ecch = _num((ea.get("volume") or {}).get("ECCH_chutes_totais"), 14.0)

    mod, _ = _build_modulators(team, kxl, is_home)
    ecpc = mod.get("ecpc", 1.0)
    energia_adj = energia * ecpc

    lethality_boost = 1.0 + 0.18 * lethality.index
    vcar_raw = (
        (0.42 * espaco + 0.33 * energia_adj + 0.17 * (ecch / 18.0) + 0.08 * lethality.index)
        * tempo
        * fsc
        * mod.get("vcar", 1.0)
        * lethality_boost
    )
    vesc = _vesc_from_entry(entry, mod_esc=mod.get("vesc", 1.0))
    v_eff = vcar_raw * (1.0 - 0.35 * opponent_vesc)

    return TeamCollisionVectors(
        team=resolve_baseline_team(team),
        energia=round(energia_adj, 4),
        espaco=round(espaco, 4),
        tempo=round(tempo, 4),
        vcar_raw=round(vcar_raw, 4),
        vesc=round(vesc, 4),
        v_eff=round(v_eff, 4),
        sectors=sectors,
        lethality=lethality,
        modulators=dict(mod),
    )


def _fept_atrito(kxl: WcKxlMatchInput | None) -> float:
    if not kxl or not kxl.fept:
        return 0.0
    atrito = 0.0
    h_players = fept_players_for_side(kxl.fept, is_home=True)
    a_players = fept_players_for_side(kxl.fept, is_home=False)
    h_atk = _avg_line_rating(h_players, "attack")
    a_def = _avg_line_rating(a_players, "defense")
    if h_atk is not None and a_def is not None and h_atk - a_def >= 0.8:
        atrito += 0.15
    a_atk = _avg_line_rating(a_players, "attack")
    h_def = _avg_line_rating(h_players, "defense")
    if a_atk is not None and h_def is not None and a_atk - h_def >= 0.8:
        atrito += 0.15
    return min(atrito, 0.30)


def _sector_note(home: TeamCollisionVectors, away: TeamCollisionVectors) -> str:
    best_h = max(home.sectors, key=lambda s: s.score)
    best_a = max(away.sectors, key=lambda s: s.score)
    if best_h.score >= best_a.score * 1.05:
        return f"Colisão favorece {home.team} pelo setor {best_h.label}"
    if best_a.score >= best_h.score * 1.05:
        return f"Colisão favorece {away.team} pelo setor {best_a.label}"
    return "Colisão setorial equilibrada"


def _lethality_note(home: TeamCollisionVectors, away: TeamCollisionVectors) -> str:
    if home.lethality.index >= away.lethality.index * 1.08:
        return (
            f"Letalidade×GK favorece {home.team} "
            f"(via {home.lethality.dominant} vs fraqueza do goleiro)"
        )
    if away.lethality.index >= home.lethality.index * 1.08:
        return (
            f"Letalidade×GK favorece {away.team} "
            f"(via {away.lethality.dominant} vs fraqueza do goleiro)"
        )
    return "Letalidade×GK equilibrada entre as seleções"


def _eacp_draw_bias(home_entry: dict, away_entry: dict) -> float:
    eacp_h = _eacp_from_entry(home_entry)
    eacp_a = _eacp_from_entry(away_entry)
    avg_chances = (eacp_h + eacp_a) / 2.0
    bias = 0.0
    if avg_chances > 1.55:
        bias += min(0.05, (avg_chances - 1.55) * 0.04)
    ecpe_avg = (_ecpe_from_entry(home_entry) + _ecpe_from_entry(away_entry)) / 2.0
    if ecpe_avg >= 16.0:
        bias += min(0.03, (ecpe_avg - 16.0) * 0.005)
    return bias


def collision_predict(
    home_team: str,
    away_team: str,
    kxl_match: WcKxlMatchInput | None = None,
) -> CollisionPredictResult | None:
    home_entry = _baseline_entry(home_team)
    away_entry = _baseline_entry(away_team)
    if not home_entry or not away_entry:
        return None

    home_key = resolve_baseline_team(home_team)
    away_key = resolve_baseline_team(away_team)

    vesc_a_pre = _vesc_from_entry(away_entry)
    vesc_h_pre = _vesc_from_entry(home_entry)
    home = _team_vectors(home_key, home_entry, away_entry, vesc_a_pre, kxl_match, is_home=True)
    away = _team_vectors(away_key, away_entry, home_entry, vesc_h_pre, kxl_match, is_home=False)

    all_notes: list[str] = []
    _, nh = _build_modulators(home_key, kxl_match, True)
    _, na = _build_modulators(away_key, kxl_match, False)
    all_notes.extend(nh)
    all_notes.extend(na)

    v_delta = home.v_eff - away.v_eff
    ttbp_h = _num((home_entry.get("historico_atrito_temporal") or {}).get("TTBP_provocado_segundos"), 1650.0)
    ttbp_a = _num((away_entry.get("historico_atrito_temporal") or {}).get("TTBP_provocado_segundos"), 1650.0)
    t_draw = abs(ttbp_h - ttbp_a) / TBRTL_REF_SEC * 0.15

    chaos = (
        _num((home_entry.get("historico_atrito_temporal") or {}).get("FSC_fator_caos_base"), 1.0)
        + _num((away_entry.get("historico_atrito_temporal") or {}).get("FSC_fator_caos_base"), 1.0)
    ) / 2.0 - 1.0

    draw_bias = 0.0
    if kxl_match:
        if kxl_match.feem:
            draw_bias += home.modulators.get("draw_bias", 0) + away.modulators.get("draw_bias", 0)
        if kxl_match.fecl:
            draw_bias += home.modulators.get("draw_bias", 0)
    atrito = _fept_atrito(kxl_match)
    if atrito > 0:
        all_notes.append(f"FEPT: gap atacante−defensor ≥0.8 — atrito +{atrito:.0%} (PDF)")

    eacp_bias = _eacp_draw_bias(home_entry, away_entry)
    if eacp_bias > 0:
        all_notes.append(
            f"EACP alto ({home.lethality.eacp}/{away.lethality.eacp} chances perdidas) — mais empate"
        )
    draw_bias += eacp_bias

    p_home_raw = _sigmoid(4.0 * v_delta)
    p_draw = _clamp(
        0.22 - abs(v_delta) * 0.35 + t_draw + chaos * 0.05 + draw_bias + atrito * 0.04,
        0.08,
        0.38,
    )
    scale = 1.0 - p_draw
    prob_home = p_home_raw * scale
    prob_away = (1.0 - p_home_raw) * scale
    total = prob_home + p_draw + prob_away

    return CollisionPredictResult(
        prob_home=prob_home / total,
        prob_draw=p_draw / total,
        prob_away=prob_away / total,
        home=home,
        away=away,
        sector_note=_sector_note(home, away),
        lethality_note=_lethality_note(home, away),
        v_delta=round(v_delta, 4),
        notes=all_notes,
    )


def collision_to_breakdown(result: CollisionPredictResult) -> dict:
    def _letalidade(lm: LethalityGkMatrix) -> dict:
        return {
            "dominant": lm.dominant,
            "index": lm.index,
            "eacp": lm.eacp,
            "metodos": [
                {
                    "metodo": c.method,
                    "ataque_pct": c.attack_pct,
                    "gk_fraco_pct": c.gk_weak_pct,
                    "pressao": c.pressure,
                }
                for c in lm.cells
            ],
        }

    def _team_vec(tv: TeamCollisionVectors) -> dict:
        return {
            "energia": tv.energia,
            "espaco": tv.espaco,
            "tempo": tv.tempo,
            "vcar_raw": tv.vcar_raw,
            "vesc": tv.vesc,
            "v_eff": tv.v_eff,
            "modulators": tv.modulators,
            "letalidade_gk": _letalidade(tv.lethality),
            "setores": [
                {
                    "setor": s.label,
                    "dna": round(s.attack_dna, 2),
                    "permissividade": round(s.defense_permissivity, 3),
                    "colisao": s.score,
                }
                for s in tv.sectors
            ],
        }

    return {
        "1": round(result.prob_home, 3),
        "X": round(result.prob_draw, 3),
        "2": round(result.prob_away, 3),
        "v_delta": result.v_delta,
        "sector_note": result.sector_note,
        "letalidade_note": result.lethality_note,
        "mandante": _team_vec(result.home),
        "visitante": _team_vec(result.away),
        "notes": result.notes,
        "doc": "docs/kxl-colisao.md",
    }


def format_collision_context(result: CollisionPredictResult) -> str:
    h, a = result.home, result.away
    lines = [
        "## Colisão KXL (Vcar × Vesc)",
        "",
        f"### {h.team}",
        f"- V_eff: {h.v_eff:.3f} | Vcar: {h.vcar_raw:.3f} | Vesc: {h.vesc:.3f}",
        f"- Energia: {h.energia:.2f} | Espaço: {h.espaco:.2f} | Tempo (TBRTL): {h.tempo:.2f}",
        "",
        f"### {a.team}",
        f"- V_eff: {a.v_eff:.3f} | Vcar: {a.vcar_raw:.3f} | Vesc: {a.vesc:.3f}",
        f"- Energia: {a.energia:.2f} | Espaço: {a.espaco:.2f} | Tempo (TBRTL): {a.tempo:.2f}",
        "",
        "### Resultado da colisão",
        f"- {result.sector_note}",
        f"- {result.lethality_note}",
        f"- Δ(V_eff): {result.v_delta:+.3f}",
        f"- 1={result.prob_home:.0%} X={result.prob_draw:.0%} 2={result.prob_away:.0%}",
    ]
    if result.notes:
        lines.append("- Moduladores: " + "; ".join(result.notes[:4]))
    return "\n".join(lines)
