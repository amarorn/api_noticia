"""Baselines KXL (DNA tático por seleção) para Copa 2026."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from schemas.national_teams import normalize_national_team

BASELINES_PATH = Path(__file__).resolve().parent.parent / "data" / "wc" / "team_baselines.json"

KXL_TEAM_ALIASES: dict[str, str] = {
    "Países Baixos": "Holanda",
    "Chéquia": "República Tcheca",
    "Bósnia e Herzegovina": "Bósnia",
    "República Democrática do Congo": "República Democrática do Congo",
    "Curaçao": "Curaçau",
}


@dataclass(frozen=True)
class WcBaselineSnapshot:
    team: str
    attack_index: float
    defense_index: float
    control_index: float
    gk_index: float
    chaos: float
    shots_per_game: float
    possession_pct: float
    counter_attack: float
    inside_goal_pct: float
    gk_inside_weakness_pct: float


@dataclass(frozen=True)
class DnaMatchup:
    home_edge: float
    away_edge: float
    sector_note: str
    home_attack_vs_away_def: float
    away_attack_vs_home_def: float


@dataclass(frozen=True)
class BaselineOutcome:
    prob_home: float
    prob_draw: float
    prob_away: float
    matchup: DnaMatchup
    home: WcBaselineSnapshot | None
    away: WcBaselineSnapshot | None


def resolve_baseline_team(name: str) -> str:
    cleaned = normalize_national_team(name.strip())
    return KXL_TEAM_ALIASES.get(cleaned, cleaned)


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _extract_snapshot(team: str, entry: dict) -> WcBaselineSnapshot:
    axes = entry.get("baseline_eixos") or {}
    ea = axes.get("ataque_ea") or {}
    ec = axes.get("conectividade_ec") or {}
    ed = axes.get("defensivo_ed") or {}
    eg = axes.get("goleiro_baliza_eg") or {}
    temporal = entry.get("historico_atrito_temporal") or {}

    dna = ea.get("DNA_direcional") or {}
    letal = ea.get("letalidade_metodo") or {}
    volume = ea.get("volume") or {}
    perm = ed.get("permissividade_setor") or {}
    gk_weak = eg.get("fraquezas") or {}

    shots = _num(volume.get("ECCH_chutes_totais"), 12.0)
    counter = _num(volume.get("EACA_contra_ataque"), 1.0)
    inside = _num(letal.get("EAGD_dentro"), 45.0)
    possession = _num(ec.get("ECPB_posse_media"), 50.0)
    passes_ok = _num(ec.get("ECPC_passes_certos_pct"), 80.0)
    dribles = _num(ec.get("ECDC_dribles_jogo"), 7.0)
    disarms = _num(ed.get("EDDF_desarmes_cortes"), 20.0)
    shots_conceded = _num(ed.get("EDCT_chutes_sofridos"), 10.0)
    gk_saves = _num(eg.get("EGDP_defesas_jogo"), 2.5)
    gk_inside_weak = _num(gk_weak.get("EGSD_sofrido_dentro"), 70.0)
    perm_avg = (
        _num(perm.get("EGFD_sofrido_dir"), 0.3)
        + _num(perm.get("EGFE_sofrido_esq"), 0.3)
        + _num(perm.get("EGFM_sofrido_meio"), 0.3)
    ) / 3.0
    chaos = _num(temporal.get("FSC_fator_caos_base"), 1.0)
    dna_peak = max(_num(dna.get("EADR_dir")), _num(dna.get("EAES_esq")), _num(dna.get("EAME_meio")), 1.0)

    attack_index = (
        shots / 18.0 * 0.35
        + counter / 3.0 * 0.15
        + inside / 55.0 * 0.25
        + dna_peak / 5.0 * 0.25
    )
    defense_index = (
        disarms / 26.0 * 0.4
        + (12.0 - min(shots_conceded, 12.0)) / 12.0 * 0.35
        + (0.5 - min(perm_avg, 0.5)) / 0.5 * 0.25
    )
    control_index = possession / 65.0 * 0.5 + passes_ok / 90.0 * 0.3 + dribles / 12.0 * 0.2
    gk_index = gk_saves / 3.5 * 0.5 + (100.0 - gk_inside_weak) / 100.0 * 0.5

    return WcBaselineSnapshot(
        team=team,
        attack_index=round(attack_index, 4),
        defense_index=round(defense_index, 4),
        control_index=round(control_index, 4),
        gk_index=round(gk_index, 4),
        chaos=chaos,
        shots_per_game=shots,
        possession_pct=possession,
        counter_attack=counter,
        inside_goal_pct=inside,
        gk_inside_weakness_pct=gk_inside_weak,
    )


def _sector_matchup(home_entry: dict, away_entry: dict) -> tuple[float, str]:
    h_ea = (home_entry.get("baseline_eixos") or {}).get("ataque_ea") or {}
    a_ed = (away_entry.get("baseline_eixos") or {}).get("defensivo_ed") or {}
    h_dna = h_ea.get("DNA_direcional") or {}
    a_perm = a_ed.get("permissividade_setor") or {}

    sectors = [
        ("direita", "EADR_dir", "EGFD_sofrido_dir"),
        ("esquerda", "EAES_esq", "EGFE_sofrido_esq"),
        ("meio", "EAME_meio", "EGFM_sofrido_meio"),
    ]
    best_side = ""
    best_score = 0.0
    for label, atk_key, def_key in sectors:
        atk = _num(h_dna.get(atk_key))
        weakness = _num(a_perm.get(def_key), 0.3)
        score = atk * weakness
        if score > best_score:
            best_score = score
            best_side = label
    return best_score, best_side


@lru_cache(maxsize=1)
def load_team_baselines() -> dict[str, dict]:
    if not BASELINES_PATH.is_file():
        return {}
    data = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    by_name: dict[str, dict] = {}
    for entry in data.get("teams", []):
        raw = entry.get("selecao", "")
        key = resolve_baseline_team(raw)
        if key not in by_name:
            by_name[key] = entry
    return by_name


def get_baseline_snapshot(team: str) -> WcBaselineSnapshot | None:
    entry = load_team_baselines().get(resolve_baseline_team(team))
    if not entry:
        return None
    return _extract_snapshot(resolve_baseline_team(team), entry)


def compute_dna_matchup(home_team: str, away_team: str) -> DnaMatchup | None:
    baselines = load_team_baselines()
    home_key = resolve_baseline_team(home_team)
    away_key = resolve_baseline_team(away_team)
    home_entry = baselines.get(home_key)
    away_entry = baselines.get(away_key)
    if not home_entry or not away_entry:
        return None

    home = _extract_snapshot(home_key, home_entry)
    away = _extract_snapshot(away_key, away_entry)

    home_attack_vs_away_def = home.attack_index * (1.0 - away.defense_index * 0.5) * away.gk_inside_weakness_pct / 100.0
    away_attack_vs_home_def = away.attack_index * (1.0 - home.defense_index * 0.5) * home.gk_inside_weakness_pct / 100.0
    sector_h, side_h = _sector_matchup(home_entry, away_entry)
    sector_a, side_a = _sector_matchup(away_entry, home_entry)
    home_edge = home_attack_vs_away_def + sector_h * 0.15
    away_edge = away_attack_vs_home_def + sector_a * 0.15

    if sector_h >= sector_a and side_h:
        sector_note = f"vantagem {home_key} pelo setor {side_h}"
    elif side_a:
        sector_note = f"vantagem {away_key} pelo setor {side_a}"
    else:
        sector_note = "matchup setorial equilibrado"

    return DnaMatchup(
        home_edge=round(home_edge, 4),
        away_edge=round(away_edge, 4),
        sector_note=sector_note,
        home_attack_vs_away_def=round(home_attack_vs_away_def, 4),
        away_attack_vs_home_def=round(away_attack_vs_home_def, 4),
    )


def baseline_outcome_probs(
    home_team: str,
    away_team: str,
    kxl_match=None,
) -> BaselineOutcome | None:
    from pipelines.wc_kxl_collision import collision_predict

    collision = collision_predict(home_team, away_team, kxl_match)
    if collision is None:
        return None
    home = get_baseline_snapshot(home_team)
    away = get_baseline_snapshot(away_team)
    matchup = compute_dna_matchup(home_team, away_team)
    if not home or not away or not matchup:
        return None
    return BaselineOutcome(
        prob_home=collision.prob_home,
        prob_draw=collision.prob_draw,
        prob_away=collision.prob_away,
        matchup=matchup,
        home=home,
        away=away,
    )


def blend_with_baseline(
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    home_team: str,
    away_team: str,
    weight: float = 0.25,
    kxl_match=None,
) -> tuple[float, float, float, BaselineOutcome | None]:
    baseline = baseline_outcome_probs(home_team, away_team, kxl_match=kxl_match)
    if baseline is None or weight <= 0:
        return prob_home, prob_draw, prob_away, baseline
    w = min(max(weight, 0.0), 0.5)
    hist = 1.0 - w
    ph = hist * prob_home + w * baseline.prob_home
    pd = hist * prob_draw + w * baseline.prob_draw
    pa = hist * prob_away + w * baseline.prob_away
    total = ph + pd + pa
    return ph / total, pd / total, pa / total, baseline


def format_baseline_context(
    home_team: str,
    away_team: str,
    baseline: BaselineOutcome | None,
) -> str:
    if baseline is None or baseline.home is None or baseline.away is None:
        return ""
    h, a = baseline.home, baseline.away
    m = baseline.matchup
    lines = [
        "## Perfil tático KXL (baseline Copa 2026)",
        "",
        f"### {h.team}",
        f"- Ataque: {h.attack_index:.2f} | Defesa: {h.defense_index:.2f} | Controle: {h.control_index:.2f}",
        f"- Chutes/jogo: {h.shots_per_game:.1f} | Posse: {h.possession_pct:.0f}% | Contra-ataque: {h.counter_attack:.1f}",
        "",
        f"### {a.team}",
        f"- Ataque: {a.attack_index:.2f} | Defesa: {a.defense_index:.2f} | Controle: {a.control_index:.2f}",
        f"- Chutes/jogo: {a.shots_per_game:.1f} | Posse: {a.possession_pct:.0f}% | Fraqueza GK dentro da área: {a.gk_inside_weakness_pct:.0f}%",
        "",
        "### Matchup DNA",
        f"- {m.sector_note}",
        f"- Pressão ofensiva {h.team}: {m.home_attack_vs_away_def:.2f} | {a.team}: {m.away_attack_vs_home_def:.2f}",
        f"- Palpite vetorial (sem histórico): 1={baseline.prob_home:.0%} X={baseline.prob_draw:.0%} 2={baseline.prob_away:.0%}",
    ]
    return "\n".join(lines)
