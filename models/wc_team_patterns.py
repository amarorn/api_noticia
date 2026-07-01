"""Padrões estatísticos 9/10–10/10 por seleção (KXL Pro) e montagem de bilhetes combo.

Fonte: últimas 10 partidas de cada seleção na Copa — linhas Over/Under por eixo
(gols, cartões, chutes, escanteios) com taxa de acerto documentada.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.national_teams import normalize_national_team

PATTERNS_PATH = Path("data/wc/team_betting_patterns.json")

# Prioridade de eixos para combo principal (menos correlacionados entre si).
_AXIS_PRIORITY: dict[str, float] = {
    "yellow_cards": 1.25,
    "goals": 1.15,
    "shots": 1.05,
    "shots_on_target": 1.0,
    "corners": 0.95,
    "goalkeeper_saves": 0.85,
}

# Eixos correlacionados — não empilhar no mesmo bilhete combo.
_CORRELATED_AXIS: list[frozenset[str]] = [
    frozenset({"goals", "shots_on_target"}),
    frozenset({"shots", "shots_on_target"}),
    frozenset({"goals", "goalkeeper_saves"}),
]

_PERIOD_LABEL = {
    "first_half": "Primeiro Tempo",
    "full_time": "Partida",
}

_STAT_LABEL = {
    "goals": "Total de Gols",
    "corners": "Total de Escanteios",
    "shots": "Total de Chutes",
    "shots_on_target": "Total de Chutes a Gol",
    "yellow_cards": "Total de Cartões Amarelos",
    "goalkeeper_saves": "Defesas do Goleiro",
}

_DIRECTION_LABEL = {
    "over": "Mais de",
    "under": "Menos de",
    "more_than_opponent": "Mais que adversário",
}


def _canonical_team(name: str) -> str:
    """Normaliza nome para chave do JSON de padrões (inglês FIFA/Sofascore)."""
    pt = normalize_national_team(name)
    # Mapa PT → EN para times no JSON (58 seleções WC 2026).
    pt_to_en: dict[str, str] = {
        "Brasil": "Brazil",
        "Alemanha": "Germany",
        "Espanha": "Spain",
        "França": "France",
        "Inglaterra": "England",
        "Holanda": "Netherlands",
        "Bélgica": "Belgium",
        "Itália": "Italy",
        "Portugal": "Portugal",
        "México": "Mexico",
        "Uruguai": "Uruguay",
        "Colômbia": "Colombia",
        "Equador": "Ecuador",
        "Paraguai": "Paraguay",
        "Estados Unidos": "USA",
        "Canadá": "Canada",
        "Coreia do Sul": "South Korea",
        "Japão": "Japan",
        "Austrália": "Australia",
        "Arábia Saudita": "Saudi Arabia",
        "Irã": "Iran",
        "Catar": "Qatar",
        "Egito": "Egypt",
        "Marrocos": "Morocco",
        "Senegal": "Senegal",
        "Gana": "Ghana",
        "Costa do Marfim": "Ivory Coast",
        "Tunísia": "Tunisia",
        "Argélia": "Algeria",
        "África do Sul": "South Africa",
        "Croácia": "Croatia",
        "Suíça": "Switzerland",
        "Áustria": "Austria",
        "Polônia": "Poland",
        "Suécia": "Sweden",
        "Dinamarca": "Denmark",
        "Noruega": "Norway",
        "Escócia": "Scotland",
        "Ucrânia": "Ukraine",
        "Hungria": "Hungary",
        "Romênia": "Romania",
        "República Tcheca": "Czech Republic",
        "Bósnia": "Bosnia & Herzegovina",
        "Turquia": "Türkiye",
        "Panamá": "Panama",
        "Haiti": "Haiti",
        "Curaçau": "Curaçao",
        "Nova Zelândia": "New Zealand",
        "China": "China",
        "Jordânia": "Jordan",
        "Palestina": "Palestine",
        "Emirados Árabes Unidos": "United Arab Emirates",
        "Barein": "Bahrain",
        "Iraque": "Iraq",
        "Cabo Verde": "Cape Verde Islands",
        "República Democrática do Congo": "Congo DR",
        "Uzbequistão": "Uzbekistan",
    }
    if name in _load_patterns()["teams"]:
        return name
    if pt in pt_to_en and pt_to_en[pt] in _load_patterns()["teams"]:
        return pt_to_en[pt]
    for en in _load_patterns()["teams"]:
        if normalize_national_team(en) == pt:
            return en
    return name


@lru_cache(maxsize=1)
def _load_patterns() -> dict[str, Any]:
    if not PATTERNS_PATH.is_file():
        return {"teams": {}, "team_count": 0}
    return json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))


def get_team_patterns(team: str) -> dict[str, Any] | None:
    """Retorna bloco de padrões de uma seleção ou None."""
    key = _canonical_team(team)
    return _load_patterns()["teams"].get(key)


def pattern_accuracy_score(home_team: str, away_team: str) -> dict[str, Any]:
    """Score 0–1 baseado nos padrões 9/10–10/10 das duas seleções."""
    home = get_team_patterns(home_team)
    away = get_team_patterns(away_team)
    if not home and not away:
        return {
            "score": 0.0,
            "label": "sem_dados",
            "reason": "Nenhum padrão KXL cadastrado para estes times.",
            "home_hit_rate": None,
            "away_hit_rate": None,
            "pattern_count": 0,
        }

    def _avg_hit(block: dict[str, Any] | None) -> float | None:
        if not block:
            return None
        rates: list[float] = []
        for patterns in block.get("axes", {}).values():
            for p in patterns:
                rates.append(float(p.get("hit_rate") or 0))
        return round(sum(rates) / len(rates), 3) if rates else None

    home_avg = _avg_hit(home)
    away_avg = _avg_hit(away)
    count = sum(
        len(v) for v in (home or {}).get("axes", {}).values()
    ) + sum(len(v) for v in (away or {}).get("axes", {}).values())

    avgs = [a for a in (home_avg, away_avg) if a is not None]
    raw = sum(avgs) / len(avgs) if avgs else 0.0
    # Escala: 0.9 → ~0.72, 1.0 → 0.85 no boost de confiança
    score = min(0.85, max(0.0, (raw - 0.85) * 1.2 + 0.5)) if raw else 0.0

    if score >= 0.75:
        label = "alta"
        reason = (
            f"Padrões KXL 9/10–10/10 fortes para "
            f"{normalize_national_team(home_team)} e {normalize_national_team(away_team)} "
            f"({count} linhas históricas)."
        )
    elif score >= 0.45:
        label = "media"
        reason = (
            f"Padrões parciais — pelo menos uma seleção com histórico KXL "
            f"({count} linhas)."
        )
    else:
        label = "baixa"
        reason = "Poucos padrões confiáveis para este confronto."

    return {
        "score": round(score, 3),
        "label": label,
        "reason": reason,
        "home_hit_rate": home_avg,
        "away_hit_rate": away_avg,
        "pattern_count": count,
    }


def _superbet_label(
    *,
    stat: str,
    period: str,
    direction: str,
    line: float | None,
    team_name: str | None,
    entity: str,
) -> str:
    period_pt = _PERIOD_LABEL.get(period, period)
    stat_pt = _STAT_LABEL.get(stat, stat)

    if direction == "more_than_opponent" and team_name:
        return f"{team_name} — {stat_pt} (mais que adversário) — {period_pt}"

    scope = team_name if entity in {"team", "opponent", "opponent_gk"} and team_name else "Partida"
    dir_pt = _DIRECTION_LABEL.get(direction, direction)
    line_s = f" {line}" if line is not None else ""
    if entity == "match_total":
        return f"{period_pt} — {stat_pt} na Partida: {dir_pt}{line_s}"
    return f"{period_pt} — {stat_pt} ({scope}): {dir_pt}{line_s}"


def _resolve_team_name(entity: str, home_en: str, away_en: str) -> str | None:
    if entity == "team":
        return normalize_national_team(home_en)
    if entity == "opponent":
        return normalize_national_team(away_en)
    if entity == "opponent_gk":
        return normalize_national_team(away_en)
    return None


def _leg_key(leg: dict[str, Any]) -> str:
    return (
        f"{leg.get('entity', '')}:{leg.get('team_side', '')}:"
        f"{leg['stat']}:{leg['period']}:{leg['direction']}:{leg.get('line')}"
    )


def _with_line(leg: dict[str, Any], line: float, home_en: str, away_en: str) -> dict[str, Any]:
    """Atualiza linha e rótulo Superbet da perna."""
    team_label = None
    entity = leg.get("entity", "match_total")
    if entity == "team":
        team_label = normalize_national_team(home_en if leg.get("team_side") == "home" else away_en)
    elif entity == "opponent":
        team_label = normalize_national_team(away_en if leg.get("team_side") == "home" else home_en)
    label = _superbet_label(
        stat=leg["stat"],
        period=leg["period"],
        direction=leg["direction"],
        line=line,
        team_name=team_label,
        entity=entity if entity != "match_total" else "match_total",
    )
    return {**leg, "line": line, "label": label}


def _apply_study_conservative_line(
    leg: dict[str, Any],
    home_en: str,
    away_en: str,
) -> dict[str, Any]:
    """Linha conservadora estilo PADRÕES DN (Under mais apertado ainda coberto pelo padrão)."""
    line = leg.get("line")
    if leg.get("direction") != "under" or line is None:
        return leg
    new_line: float | None = None
    if (
        leg.get("stat") == "goals"
        and leg.get("period") == "first_half"
        and leg.get("entity") == "match_total"
        and line >= 2.0
    ):
        new_line = 1.5
    elif (
        leg.get("stat") == "goals"
        and leg.get("period") == "full_time"
        and leg.get("entity") == "match_total"
        and line >= 3.5
    ):
        new_line = 3.5
    if new_line is not None and abs(new_line - line) > 1e-9:
        return _with_line(leg, new_line, home_en, away_en)
    return leg


def _axes_correlated(a: str, b: str) -> bool:
    for group in _CORRELATED_AXIS:
        if a in group and b in group:
            return True
    return a == b


def _build_legs(home_team: str, away_team: str) -> list[dict[str, Any]]:
    """Monta pernas candidatas cruzando padrões das duas seleções."""
    home_en = _canonical_team(home_team)
    away_en = _canonical_team(away_team)
    home_block = get_team_patterns(home_team)
    away_block = get_team_patterns(away_team)
    legs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_leg(pattern: dict[str, Any], *, side: str, team_en: str) -> None:
        entity = pattern["entity"]
        if entity == "match_total":
            team_label = None
        else:
            team_label = _resolve_team_name(
                entity if side == "home" else ("team" if entity == "opponent" else entity),
                home_en,
                away_en,
            )
            if entity == "team":
                team_label = normalize_national_team(team_en)
            elif entity == "opponent":
                team_label = normalize_national_team(away_en if team_en == home_en else home_en)

        label = _superbet_label(
            stat=pattern["stat"],
            period=pattern["period"],
            direction=pattern["direction"],
            line=pattern.get("line"),
            team_name=team_label,
            entity=entity if entity != "match_total" else "match_total",
        )
        leg = {
            "stat": pattern["stat"],
            "period": pattern["period"],
            "direction": pattern["direction"],
            "line": pattern.get("line"),
            "entity": entity,
            "team_side": side,
            "hit_rate": pattern["hit_rate"],
            "hits": pattern["hits"],
            "total": pattern["total"],
            "label": label,
            "pattern_ref": f"PADRÕES KXL — {normalize_national_team(team_en)} {pattern['hits']}/{pattern['total']}",
            "score": round(
                pattern["hit_rate"] * _AXIS_PRIORITY.get(pattern["stat"], 1.0)
                * (1.08 if pattern["period"] == "first_half" else 1.0),
                4,
            ),
        }
        key = _leg_key(leg)
        if key in seen:
            return
        seen.add(key)
        legs.append(leg)

    for block, side, team_en in (
        (home_block, "home", home_en),
        (away_block, "away", away_en),
    ):
        if not block:
            continue
        for patterns in block.get("axes", {}).values():
            for p in patterns:
                add_leg(p, side=side, team_en=team_en)

    # Reforço: linhas "Soma dos dois" presentes nos dois times (interseção).
    if home_block and away_block:
        for axis, home_patterns in home_block.get("axes", {}).items():
            away_patterns = away_block.get("axes", {}).get(axis, [])
            home_totals = [p for p in home_patterns if p.get("entity") == "match_total"]
            away_totals = [p for p in away_patterns if p.get("entity") == "match_total"]
            for hp in home_totals:
                for ap in away_totals:
                    if hp["period"] != ap["period"] or hp["direction"] != ap["direction"]:
                        continue
                    if hp["direction"] in {"over", "under"} and hp.get("line") is not None:
                        if hp["direction"] == "under":
                            line = min(hp["line"], ap["line"])
                        else:
                            line = max(hp["line"], ap["line"])
                    else:
                        line = hp.get("line")
                    merged = {
                        **hp,
                        "line": line,
                        "hit_rate": round((hp["hit_rate"] + ap["hit_rate"]) / 2, 2),
                        "hits": min(hp["hits"], ap["hits"]),
                        "total": hp["total"],
                        "home_hits": hp["hits"],
                        "home_total": hp["total"],
                        "away_hits": ap["hits"],
                        "away_total": ap["total"],
                    }
                    label = _superbet_label(
                        stat=merged["stat"],
                        period=merged["period"],
                        direction=merged["direction"],
                        line=merged.get("line"),
                        team_name=None,
                        entity="match_total",
                    )
                    leg = {
                        "stat": merged["stat"],
                        "period": merged["period"],
                        "direction": merged["direction"],
                        "line": merged.get("line"),
                        "entity": "match_total",
                        "team_side": "both",
                        "hit_rate": merged["hit_rate"],
                        "hits": merged["hits"],
                        "total": merged["total"],
                        "label": label,
                        "pattern_ref": (
                            f"PADRÕES KXL — cruzamento "
                            f"{normalize_national_team(home_en)} {hp['hits']}/{hp['total']} × "
                            f"{normalize_national_team(away_en)} {ap['hits']}/{ap['total']}"
                        ),
                        "score": round(
                            merged["hit_rate"]
                            * _AXIS_PRIORITY.get(merged["stat"], 1.0)
                            * 1.12
                            * (1.08 if merged["period"] == "first_half" else 1.0),
                            4,
                        ),
                    }
                    key = _leg_key(leg)
                    if key not in seen:
                        seen.add(key)
                        legs.append(leg)

    legs.sort(key=lambda x: (-x["score"], -x["hit_rate"]))
    return legs


def _leg_rank_key(leg: dict[str, Any]) -> tuple[float, float, int, int, int]:
    """Prioriza score KXL, acerto histórico e padrões de cruzamento match_total."""
    ref = str(leg.get("pattern_ref", ""))
    return (
        float(leg.get("score") or 0),
        float(leg.get("hit_rate") or 0),
        1 if "cruzamento" in ref else 0,
        1 if leg.get("entity") == "match_total" else 0,
        1 if leg.get("period") == "first_half" else 0,
    )


def _pick_combo(legs: list[dict[str, Any]], size: int = 2) -> list[dict[str, Any]]:
    """Monta combo pelos eixos com maior score KXL (decorrelacionados)."""
    candidates = [leg for leg in legs if float(leg.get("hit_rate") or 0) >= 0.9]
    ranked = sorted(candidates, key=_leg_rank_key, reverse=True)

    picked: list[dict[str, Any]] = []
    for leg in ranked:
        if len(picked) >= size:
            break
        if any(_axes_correlated(leg["stat"], p["stat"]) for p in picked):
            continue
        if any(p["stat"] == leg["stat"] and p["period"] == leg["period"] for p in picked):
            continue
        picked.append(leg)
    return picked


def _pick_reserves(legs: list[dict[str, Any]], combo: list[dict[str, Any]], size: int = 2) -> list[dict[str, Any]]:
    """Singles reserva: próximos eixos 9/10+ ainda não usados no combo."""
    combo_keys = {_leg_key(leg) for leg in combo}
    candidates = [
        leg
        for leg in legs
        if _leg_key(leg) not in combo_keys and float(leg.get("hit_rate") or 0) >= 0.9
    ]
    ranked = sorted(candidates, key=_leg_rank_key, reverse=True)

    reserves: list[dict[str, Any]] = []
    for leg in ranked:
        if len(reserves) >= size:
            break
        pool = combo + reserves
        if any(_axes_correlated(leg["stat"], p["stat"]) for p in pool):
            continue
        reserves.append({**leg, "role": "reserva"})
    return reserves


def build_combo_ticket(
    home_team: str,
    away_team: str,
    *,
    bankroll: float = 1000.0,
    snapshot: Any | None = None,
) -> dict[str, Any]:
    """Monta bilhete combo principal + apostas reserva com base nos padrões KXL."""
    from ingest.superbet.combo_markets import enrich_combo_ticket

    home_en = _canonical_team(home_team)
    away_en = _canonical_team(away_team)
    accuracy = pattern_accuracy_score(home_team, away_team)
    legs = _build_legs(home_team, away_team)

    if len(legs) < 2:
        return {
            "available": False,
            "title": f"BILHETE — {normalize_national_team(home_team)} x {normalize_national_team(away_team)}",
            "accuracy": accuracy,
            "reason": (
                "Padrões insuficientes para montar combo seguro. "
                "Cadastre mais seleções ou aguarde confronto com histórico KXL."
            ),
            "main_bets": [],
            "reserve_bets": [],
            "strategy_notes": [],
            "suggested_stake_pct": 0.0,
            "suggested_stake_value": 0.0,
        }

    main = _pick_combo(legs, size=2)
    main = [_apply_study_conservative_line(b, home_en, away_en) for b in main]
    reserves = _pick_reserves(legs, main, size=2) if main else []
    reserves = [_apply_study_conservative_line(b, home_en, away_en) for b in reserves]

    avg_hit = sum(b["hit_rate"] for b in main) / len(main) if main else 0.0
    # Stake conservador: combo 2 pernas ~1–2.5% banca conforme acurácia histórica
    stake_pct = round(min(2.5, max(0.8, avg_hit * 2.2)), 2)
    if accuracy["score"] < 0.45:
        stake_pct = round(stake_pct * 0.6, 2)

    strategy_notes = [
        "Combo montado pelos eixos KXL com maior score neste confronto (9/10 ou 10/10).",
        "Seleção automática — não é template fixo; muda conforme padrões de cada seleção.",
        "Apostas principais em eixos decorrelacionados (ex.: cartões 1T + chutes 1T).",
        "Reservas são singles de fallback — use se o combo principal não estiver disponível na casa.",
        "Não empilhe combo + reservas no mesmo bilhete; escolha uma estrutura.",
        f"Exposição sugerida: {stake_pct:.1f}% da banca (R$ {bankroll * stake_pct / 100:.0f}).",
    ]

    if accuracy["label"] == "alta":
        strategy_notes.insert(
            0,
            "Alta acurácia histórica neste confronto — priorize linhas de 10/10 no combo.",
        )

    main_bets = [{**b, "role": "principal", "rank": i + 1} for i, b in enumerate(main)]
    ticket = {
        "available": len(main) >= 2,
        "title": f"BILHETE — {normalize_national_team(home_team)} x {normalize_national_team(away_team)}",
        "accuracy": accuracy,
        "reason": None if len(main) >= 2 else "Não foi possível achar 2 pernas decorrelacionadas com 9/10+.",
        "main_bets": main_bets,
        "reserve_bets": [{**b, "rank": i + 1} for i, b in enumerate(reserves)],
        "strategy_notes": strategy_notes,
        "suggested_stake_pct": stake_pct,
        "suggested_stake_value": round(bankroll * stake_pct / 100, 2),
        "combined_hit_rate_estimate": round(avg_hit ** len(main), 3) if main else 0.0,
    }
    enriched = enrich_combo_ticket(ticket, snapshot)
    if main_bets:
        from models.wc_combo_last10 import build_last10_analysis

        enriched["last10_analysis"] = build_last10_analysis(
            home_team,
            away_team,
            main_bets,
            client=_optional_sofascore_client(fetch_incidents=_combo_last10_fetch_incidents()),
        )
    return enriched


def _combo_last10_fetch_incidents() -> bool:
    from config import settings

    return bool(getattr(settings, "combo_last10_fetch_incidents", False))


def _optional_sofascore_client(*, fetch_incidents: bool = False) -> Any | None:
    """Cliente Sofascore para incidentes 1T; None se desativado ou indisponível."""
    if not fetch_incidents:
        return None
    try:
        from ingest.sofascore.client import SofascoreClient, SofascoreClientError

        return SofascoreClient()
    except SofascoreClientError:
        return None
    except ImportError:
        return None


def blend_confidence_with_patterns(
    base_score: float,
    home_team: str,
    away_team: str,
) -> tuple[float, str | None]:
    """Incorpora padrões KXL no score de confiança do modelo (máx. +0.12)."""
    pat = pattern_accuracy_score(home_team, away_team)
    if pat["score"] <= 0:
        return base_score, None
    boost = pat["score"] * 0.12
    new_score = min(1.0, base_score + boost)
    note = f"Padrões KXL reforçam confiança (+{boost * 100:.0f} pp): {pat['reason']}"
    return round(new_score, 3), note


__all__ = [
    "build_combo_ticket",
    "blend_confidence_with_patterns",
    "get_team_patterns",
    "pattern_accuracy_score",
]
