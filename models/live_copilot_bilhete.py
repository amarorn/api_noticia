"""Montagem e validação de bilhete sugerido pelo copiloto GPT."""
from __future__ import annotations

import re
from typing import Any

from models.bet_builder_odds import resolve_combined_odds
from models.inplay_bet_builder_guard import validate_bet_builder
from models.inplay_leg_compatibility import is_superbet_bet_builder_market


def _pick_key(market: str, outcome: str) -> str:
    return f"{market}:{str(outcome).lower()}"


def _parse_score(current_score: str | None) -> tuple[int, int]:
    if not current_score:
        return 0, 0
    parts = re.split(r"[x×:\-]", str(current_score).strip(), maxsplit=1)
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return 0, 0


def _compact_scan_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": row.get("market"),
        "outcome": row.get("outcome"),
        "label": row.get("label"),
        "model_prob": row.get("model_prob"),
        "market_odd": row.get("market_odd"),
        "expected_value": row.get("expected_value"),
        "edge_pp": row.get("edge_pp"),
        "meets_threshold": row.get("meets_threshold"),
        "suggested_stake_pct": row.get("suggested_stake_pct"),
    }


def football_bilhete_candidates(advice: dict[str, Any]) -> list[dict[str, Any]]:
    """Pool de pernas elegíveis (market_scan + oportunidades)."""
    strategy = advice.get("strategy") or {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source in (
        strategy.get("opportunities") or [],
        strategy.get("watch_list") or [],
        strategy.get("market_scan") or [],
    ):
        for row in source:
            if not isinstance(row, dict):
                continue
            market = str(row.get("market") or "")
            outcome = str(row.get("outcome") or "")
            if market == "next_goal":
                continue
            if not market or not outcome:
                continue
            if not is_superbet_bet_builder_market(market):
                continue
            odd = float(row.get("market_odd") or 0)
            if odd <= 1.0:
                continue
            key = _pick_key(market, outcome)
            if key in seen:
                continue
            if row.get("tier") == "abaixo_limiar" and source is strategy.get("opportunities"):
                continue
            seen.add(key)
            out.append(row)

    out.sort(key=lambda r: float(r.get("expected_value") or 0), reverse=True)
    return out[:20]


def basket_bilhete_candidates(advice: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in advice.get("aportes") or []:
        if not isinstance(row, dict):
            continue
        if row.get("action") not in ("apostar", "aporte", "monitorar"):
            continue
        if float(row.get("market_odd") or 0) <= 1.0:
            continue
        rows.append(row)
    rows.sort(key=lambda r: float(r.get("expected_value") or 0), reverse=True)
    return rows[:12]


def bilhete_context_football(advice: dict[str, Any]) -> dict[str, Any]:
    strategy = advice.get("strategy") or {}
    candidates = football_bilhete_candidates(advice)
    scan = [_compact_scan_row(r) for r in candidates[:14]]

    optimized = advice.get("optimized_tickets") or {}
    top_tickets: list[dict[str, Any]] = []
    for period in ("ft", "mixed", "2h", "1h"):
        for ticket in (optimized.get(period) or [])[:2]:
            if not isinstance(ticket, dict) or not ticket.get("valid"):
                continue
            top_tickets.append({
                "periodo": period,
                "combined_odd": ticket.get("combined_odd"),
                "combined_ev": ticket.get("combined_ev"),
                "combined_prob": ticket.get("combined_prob"),
                "score": ticket.get("score"),
                "pernas": [
                    {
                        "market": leg.get("market"),
                        "outcome": leg.get("outcome"),
                        "label": leg.get("label"),
                        "market_odd": leg.get("market_odd"),
                        "expected_value": leg.get("expected_value"),
                    }
                    for leg in (ticket.get("legs") or [])
                    if isinstance(leg, dict)
                ],
            })
            if len(top_tickets) >= 4:
                break
        if len(top_tickets) >= 4:
            break

    combo = strategy.get("combo_ticket") or {}
    combo_main = [
        {
            "label": b.get("label"),
            "market_odd": b.get("market_odd"),
            "expected_value": b.get("expected_value"),
            "hit_rate": b.get("hit_rate"),
        }
        for b in (combo.get("main_bets") or [])[:4]
        if isinstance(b, dict)
    ]

    return {
        "mercados_scan": scan,
        "bilhetes_otimizados_modelo": top_tickets,
        "combo_kxl_modelo": {
            "disponivel": combo.get("available"),
            "titulo": combo.get("title"),
            "main_bets": combo_main,
            "combo_odd": combo.get("combo_odd"),
            "combo_ev": combo.get("combo_ev"),
        },
        "regras_bilhete": [
            "Use somente mercados listados em mercados_scan.",
            "Prefira 2-3 pernas com narrativas complementares (evite correlação redundante).",
            "Respeite blindagens e mercados mortos do modelo.",
            "Se nada combinar bem, tipo=nenhum.",
        ],
    }


def bilhete_context_basket(advice: dict[str, Any]) -> dict[str, Any]:
    candidates = basket_bilhete_candidates(advice)
    return {
        "mercados_scan": [_compact_scan_row(r) for r in candidates[:10]],
        "regras_bilhete": [
            "Use somente mercados do scan (moneyline, spread, total).",
            "Prefira 1-2 pernas; combo só se complementares.",
        ],
    }


def _validate_bilhete_legs(
    raw_legs: list[Any],
    *,
    by_key: dict[str, dict[str, Any]],
    allowed: set[str],
    max_legs: int = 4,
) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for raw in raw_legs:
        if not isinstance(raw, dict):
            continue
        key = _pick_key(str(raw.get("market", "")), str(raw.get("outcome", "")))
        if key not in allowed:
            continue
        source = by_key[key]
        papel = str(raw.get("papel") or "complemento").lower()
        if papel not in {"ancora", "complemento"}:
            papel = "ancora" if len(validated) == 0 else "complemento"
        validated.append({
            "rank": int(raw.get("rank") or len(validated) + 1),
            "market": source.get("market"),
            "outcome": source.get("outcome"),
            "label": source.get("label") or raw.get("label"),
            "papel": papel,
            "rationale": str(raw.get("rationale") or "").strip()[:300],
            "market_odd": source.get("market_odd"),
            "model_prob": source.get("model_prob"),
            "expected_value": source.get("expected_value"),
            "edge_pp": source.get("edge_pp"),
        })
        if len(validated) >= max_legs:
            break
    return validated


def enrich_bilhete(
    bilhete: dict[str, Any],
    *,
    advice: dict[str, Any],
    sport: str,
) -> dict[str, Any]:
    pernas = bilhete.get("pernas") or []
    if not pernas:
        bilhete["valid"] = False
        return bilhete

    leg_dicts = [
        {
            "market": p.get("market"),
            "outcome": p.get("outcome"),
            "market_odd": p.get("market_odd"),
            "model_prob": p.get("model_prob"),
            "superbet_event_id": advice.get("superbet_event_id"),
        }
        for p in pernas
    ]

    combined, simple, mode = resolve_combined_odds(leg_dicts)
    bilhete["combined_odd"] = combined
    bilhete["combined_odd_simple"] = simple
    bilhete["pricing_mode"] = mode

    warnings: list[str] = list(bilhete.get("validation_warnings") or [])
    if sport == "football":
        home_score, away_score = _parse_score(advice.get("current_score"))
        inplay = advice.get("inplay_summary") if isinstance(advice.get("inplay_summary"), dict) else {}
        validation = validate_bet_builder(
            [{"market": p["market"], "outcome": p["outcome"], "label": p.get("label")} for p in pernas],
            minute=int(advice.get("minute") or 0),
            home_score=home_score,
            away_score=away_score,
            ht_home=inplay.get("ht_home_score"),
            ht_away=inplay.get("ht_away_score"),
        )
        bilhete["valid"] = bool(validation.get("valid"))
        for w in validation.get("warnings") or []:
            if isinstance(w, dict):
                msg = w.get("reason") or w.get("message")
                if msg:
                    warnings.append(str(msg)[:200])
            elif isinstance(w, str):
                warnings.append(w[:200])
        for e in validation.get("errors") or []:
            if isinstance(e, dict):
                msg = e.get("reason") or e.get("message")
                if msg:
                    warnings.append(str(msg)[:200])
    else:
        bilhete["valid"] = len(pernas) >= 1

    bilhete["validation_warnings"] = warnings[:6]
    return bilhete


def validate_copilot_bilhete(
    parsed: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    advice: dict[str, Any],
    sport: str,
) -> dict[str, Any] | None:
    raw = parsed.get("bilhete")
    if not isinstance(raw, dict):
        return None

    tipo = str(raw.get("tipo") or "nenhum").lower()
    if tipo not in {"combo", "simples", "nenhum"}:
        tipo = "nenhum"

    by_key = {_pick_key(str(c.get("market", "")), str(c.get("outcome", ""))): c for c in candidates}
    allowed = set(by_key.keys())

    pernas = _validate_bilhete_legs(raw.get("pernas") or [], by_key=by_key, allowed=allowed)
    if tipo == "nenhum" or not pernas:
        return {
            "tipo": "nenhum",
            "titulo": str(raw.get("titulo") or "Sem combo recomendado"),
            "resumo": str(raw.get("resumo") or "").strip()[:400],
            "pernas": [],
            "valid": False,
            "avisos_correlacao": [],
            "validation_warnings": [],
            "combined_odd": None,
            "combined_odd_simple": None,
            "pricing_mode": None,
        }

    if tipo == "simples":
        pernas = pernas[:1]

    avisos = [
        str(a).strip()[:200]
        for a in (raw.get("avisos_correlacao") or [])
        if isinstance(a, str) and a.strip()
    ][:4]

    bilhete = {
        "tipo": "simples" if len(pernas) == 1 else "combo",
        "titulo": str(raw.get("titulo") or "Bilhete sugerido").strip()[:120],
        "resumo": str(raw.get("resumo") or "").strip()[:400],
        "pernas": pernas,
        "avisos_correlacao": avisos,
        "validation_warnings": [],
        "valid": False,
        "combined_odd": None,
        "combined_odd_simple": None,
        "pricing_mode": None,
    }
    return enrich_bilhete(bilhete, advice=advice, sport=sport)


def fallback_bilhete_from_optimizer(advice: dict[str, Any], *, sport: str) -> dict[str, Any] | None:
    if sport == "basketball":
        candidates = basket_bilhete_candidates(advice)
        strong = [c for c in candidates if float(c.get("expected_value") or 0) >= 0.04]
        if not strong:
            return None
        top = strong[0]
        pernas = [{
            "rank": 1,
            "market": top.get("market"),
            "outcome": top.get("outcome"),
            "label": top.get("label"),
            "papel": "ancora",
            "rationale": "Melhor EV individual do modelo in-play.",
            "market_odd": top.get("market_odd"),
            "model_prob": top.get("model_prob"),
            "expected_value": top.get("expected_value"),
            "edge_pp": top.get("edge_pp"),
        }]
        if len(strong) >= 2 and float(strong[1].get("expected_value") or 0) >= 0.03:
            s2 = strong[1]
            pernas.append({
                "rank": 2,
                "market": s2.get("market"),
                "outcome": s2.get("outcome"),
                "label": s2.get("label"),
                "papel": "complemento",
                "rationale": "Segunda melhor perna por EV.",
                "market_odd": s2.get("market_odd"),
                "model_prob": s2.get("model_prob"),
                "expected_value": s2.get("expected_value"),
                "edge_pp": s2.get("edge_pp"),
            })
        bilhete = {
            "tipo": "combo" if len(pernas) > 1 else "simples",
            "titulo": "Bilhete quantitativo (basquete)",
            "resumo": "Montado a partir das melhores pernas EV do modelo.",
            "pernas": pernas,
            "avisos_correlacao": [],
            "validation_warnings": [],
            "valid": False,
            "combined_odd": None,
            "combined_odd_simple": None,
            "pricing_mode": None,
        }
        return enrich_bilhete(bilhete, advice=advice, sport=sport)

    optimized = advice.get("optimized_tickets") or {}
    best: dict[str, Any] | None = None
    best_score = -1.0
    for period in ("ft", "mixed", "2h", "1h"):
        for ticket in optimized.get(period) or []:
            if not isinstance(ticket, dict) or not ticket.get("valid"):
                continue
            score = float(ticket.get("score") or 0)
            if score > best_score:
                best_score = score
                best = ticket

    if best is None:
        candidates = football_bilhete_candidates(advice)
        strong = [c for c in candidates if float(c.get("expected_value") or 0) >= 0.05]
        if not strong:
            return None
        top = strong[0]
        pernas = [{
            "rank": 1,
            "market": top.get("market"),
            "outcome": top.get("outcome"),
            "label": top.get("label"),
            "papel": "ancora",
            "rationale": "Melhor EV isolado do scan in-play.",
            "market_odd": top.get("market_odd"),
            "model_prob": top.get("model_prob"),
            "expected_value": top.get("expected_value"),
            "edge_pp": top.get("edge_pp"),
        }]
        bilhete = {
            "tipo": "simples",
            "titulo": "Palpite simples (modelo)",
            "resumo": "Sem combo válido no otimizador — melhor perna isolada.",
            "pernas": pernas,
            "avisos_correlacao": [],
            "validation_warnings": [],
            "valid": False,
            "combined_odd": None,
            "combined_odd_simple": None,
            "pricing_mode": None,
        }
        return enrich_bilhete(bilhete, advice=advice, sport=sport)

    pernas = []
    for idx, leg in enumerate(best.get("legs") or [], start=1):
        if not isinstance(leg, dict):
            continue
        pernas.append({
            "rank": idx,
            "market": leg.get("market"),
            "outcome": leg.get("outcome"),
            "label": leg.get("label"),
            "papel": "ancora" if idx == 1 else "complemento",
            "rationale": "Combo pré-validado pelo otimizador EV×prob.",
            "market_odd": leg.get("market_odd"),
            "model_prob": leg.get("model_prob"),
            "expected_value": leg.get("expected_value"),
            "edge_pp": leg.get("edge_pp"),
        })

    bilhete = {
        "tipo": "combo" if len(pernas) > 1 else "simples",
        "titulo": f"Bilhete otimizado ({best.get('period_mix', 'ft')})",
        "resumo": (
            f"Combo score {best_score:.2f} · EV combinado "
            f"{float(best.get('combined_ev') or 0):.1%}"
        ),
        "pernas": pernas,
        "avisos_correlacao": [],
        "validation_warnings": [],
        "valid": True,
        "combined_odd": best.get("combined_odd"),
        "combined_odd_simple": None,
        "pricing_mode": "bet_builder_sgm",
    }
    return enrich_bilhete(bilhete, advice=advice, sport=sport)
