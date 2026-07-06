"""Estratégias pareadas de blindagem — pernas complementares (se uma falha, a outra compensa)."""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from config import settings

_OPENAI_BASE = "https://api.openai.com/v1"
_TIMEOUT = 40.0

_PAIR_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "zona_2_gols",
        "name": "Zona de 2 gols",
        "leg_a": ("over_1_5", "yes"),
        "leg_b": ("over_2_5", "no"),
        "coverage_type": "total_band",
        "lose_both_pct": 0.0,
        "scenario_a": "0–1 gol: só a 2ª perna paga",
        "scenario_b": "3+ gols: só a 1ª perna paga",
        "scenario_both": "Exatamente 2 gols: as duas pernas ganham",
    },
    {
        "id": "faixa_2_3_gols",
        "name": "Faixa 2–3 gols",
        "leg_a": ("over_1_5", "yes"),
        "leg_b": ("over_3_5", "no"),
        "coverage_type": "total_band",
        "lose_both_pct": 0.0,
        "scenario_a": "0–1 gol: só Under 3.5 paga",
        "scenario_b": "4+ gols: só Over 1.5 paga",
        "scenario_both": "2–3 gols: as duas pernas ganham",
    },
    {
        "id": "jogo_fechado",
        "name": "Jogo fechado",
        "leg_a": ("btts", "no"),
        "leg_b": ("over_2_5", "no"),
        "coverage_type": "low_scoring",
        "lose_both_pct": None,
        "scenario_a": "BTTS Não + Under 2.5 cobrem 0–0 e 1–0",
        "scenario_b": "Ambas perdem se o jogo abrir (2+ gols com BTTS)",
        "scenario_both": "Placares baixos: as duas pernas ganham",
    },
    {
        "id": "mandante_nao_perde",
        "name": "Mandante não perde (split)",
        "leg_a": ("h2h", "1"),
        "leg_b": ("h2h", "X"),
        "coverage_type": "h2h_cover",
        "lose_both_outcome": "2",
        "scenario_a": "Vitória mandante: 1ª perna paga",
        "scenario_b": "Empate: 2ª perna paga",
        "scenario_both": "Vitória visitante: as duas perdem",
    },
    {
        "id": "visitante_nao_perde",
        "name": "Visitante não perde (split)",
        "leg_a": ("h2h", "2"),
        "leg_b": ("h2h", "X"),
        "coverage_type": "h2h_cover",
        "lose_both_outcome": "1",
        "scenario_a": "Vitória visitante: 1ª perna paga",
        "scenario_b": "Empate: 2ª perna paga",
        "scenario_both": "Vitória mandante: as duas perdem",
    },
    {
        "id": "dupla_chance_inversa",
        "name": "1X2 espelhado",
        "leg_a": ("h2h", "1"),
        "leg_b": ("h2h", "2"),
        "coverage_type": "h2h_cover",
        "lose_both_outcome": "X",
        "scenario_a": "Mandante vence: 1ª perna paga",
        "scenario_b": "Visitante vence: 2ª perna paga",
        "scenario_both": "Empate: as duas perdem",
    },
]

_LLM_SYSTEM = """\
Você elabora estratégias pareadas de blindagem in-play em português do Brasil.
Recebe candidatos quantitativos com duas pernas complementares (gols, 1X2, escanteios, cartões).

Regras:
1. Escolha EXATAMENTE 2 estratégias da lista "candidatos" (copie os ids).
2. Prefira diversidade: se possível, uma estratégia de gols/1X2 e outra de escanteios ou cartões.
3. Não invente mercados, odds ou probabilidades.
4. Explique quando uma perna compensa a outra (cenários de vitória).
5. Indique stakes relativas (ex.: 60/40) quando fizer sentido.
6. Responda APENAS JSON válido:
{
  "estrategias": [
    {
      "id": "id do candidato",
      "titulo": "nome curto",
      "resumo": "2-3 frases objetivas",
      "stake_split": "ex.: 50% / 50% da stake planejada",
      "cenario_chave": "quando uma perna salva a outra"
    }
  ]
}"""


def _pair_category(pair_id: str) -> str:
    if pair_id.startswith("corners_") or pair_id.startswith("zona_escanteios"):
        return "corners"
    if pair_id.startswith("cards_") or pair_id.startswith("zona_cartoes"):
        return "cards"
    if pair_id in {"mandante_nao_perde", "visitante_nao_perde", "dupla_chance_inversa"}:
        return "h2h"
    if pair_id in {"jogo_fechado"}:
        return "goals"
    if pair_id.startswith("zona_") or pair_id.startswith("faixa_"):
        return "goals"
    return "other"


def _build_dynamic_band_pairs(
    idx: dict[tuple[str, str], dict[str, Any]],
    *,
    prefix: str,
    category: str,
    name_prefix: str,
    min_band: float = 1.0,
) -> list[dict[str, Any]]:
    """Gera pares over/under complementares para escanteios ou cartões."""
    over_lines: list[tuple[float, str]] = []
    for (market, outcome), _row in idx.items():
        if not market.startswith(f"{prefix}_over_") or outcome != "yes":
            continue
        line_str = market.replace(f"{prefix}_over_", "").replace("_", ".")
        try:
            over_lines.append((float(line_str), market))
        except ValueError:
            continue
    over_lines.sort()

    templates: list[dict[str, Any]] = []
    for i, (low_val, low_market) in enumerate(over_lines):
        for high_val, high_market in over_lines[i + 1 :]:
            if high_val - low_val < min_band:
                continue
            low_label = str(low_val).replace(".", ",")
            high_label = str(high_val).replace(".", ",")
            band_mid = (low_val + high_val) / 2
            tpl_id = f"{prefix}_zona_{str(low_val).replace('.', '_')}_{str(high_val).replace('.', '_')}"
            templates.append({
                "id": tpl_id,
                "name": f"{name_prefix} {low_label}–{high_label}",
                "leg_a": (low_market, "yes"),
                "leg_b": (high_market, "no"),
                "coverage_type": "total_band",
                "lose_both_pct": 0.0,
                "scenario_a": f"Abaixo de {low_label}: só a 2ª perna paga",
                "scenario_b": f"Acima de {high_label}: só a 1ª perna paga",
                "scenario_both": f"Entre {low_label} e {high_label}: as duas pernas ganham",
                "_category": category,
                "_band_mid": band_mid,
            })
    return templates


def _index_scan(market_scan: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    idx: dict[tuple[str, str], dict[str, Any]] = {}
    for row in market_scan:
        key = (str(row.get("market") or ""), str(row.get("outcome") or "").lower())
        if key[0]:
            idx[key] = row
    return idx


def _resolve_leg(
    idx: dict[tuple[str, str], dict[str, Any]],
    market: str,
    outcome: str,
) -> dict[str, Any] | None:
    row = idx.get((market, outcome.lower()))
    if not row or float(row.get("market_odd") or 0) <= 1.01:
        return None
    return {
        "market": market,
        "outcome": outcome.lower(),
        "label": str(row.get("label") or ""),
        "model_prob": float(row.get("model_prob") or 0),
        "market_odd": float(row.get("market_odd") or 0),
        "expected_value": float(row.get("expected_value") or 0),
        "edge_pp": float(row.get("edge_pp") or 0),
        "suggested_stake_pct": float(row.get("suggested_stake_pct") or 0),
    }


def _coverage_from_inplay(
    template: dict[str, Any],
    inplay: dict[str, Any],
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
) -> dict[str, float]:
    flp = inplay.get("final_line_probs") or {}
    ctype = template.get("coverage_type")

    if ctype == "total_band":
        p_a = leg_a["model_prob"]
        p_b = leg_b["model_prob"]
        p_both = max(0.0, p_a + p_b - 1.0)
        p_both = min(p_both, min(p_a, p_b))
        lose_both = float(template.get("lose_both_pct") or 0.0)
        cover = 1.0 - lose_both
        return {
            "prob_leg_a": round(p_a, 4),
            "prob_leg_b": round(p_b, 4),
            "prob_both_win": round(p_both, 4),
            "prob_at_least_one": round(cover, 4),
            "prob_both_lose": round(lose_both, 4),
        }

    if ctype == "low_scoring":
        p_btts_no = leg_a["model_prob"]
        p_under = leg_b["model_prob"]
        p_both = max(0.0, min(p_btts_no, p_under))
        lose_both = max(0.0, 1.0 - p_btts_no - p_under + p_both)
        return {
            "prob_leg_a": round(p_btts_no, 4),
            "prob_leg_b": round(p_under, 4),
            "prob_both_win": round(p_both, 4),
            "prob_at_least_one": round(1.0 - lose_both, 4),
            "prob_both_lose": round(lose_both, 4),
        }

    if ctype == "h2h_cover":
        lose_key = str(template.get("lose_both_outcome") or "X")
        prob_map = {
            "1": float(inplay.get("prob_final_home") or leg_a["model_prob"]),
            "X": float(inplay.get("prob_final_draw") or 0),
            "2": float(inplay.get("prob_final_away") or leg_b["model_prob"]),
        }
        lose_both = prob_map.get(lose_key, 0.0)
        return {
            "prob_leg_a": round(leg_a["model_prob"], 4),
            "prob_leg_b": round(leg_b["model_prob"], 4),
            "prob_both_win": 0.0,
            "prob_at_least_one": round(1.0 - lose_both, 4),
            "prob_both_lose": round(lose_both, 4),
        }

    return {
        "prob_leg_a": round(leg_a["model_prob"], 4),
        "prob_leg_b": round(leg_b["model_prob"], 4),
        "prob_both_win": 0.0,
        "prob_at_least_one": round(max(leg_a["model_prob"], leg_b["model_prob"]), 4),
        "prob_both_lose": 0.0,
    }


def _score_pair(coverage: dict[str, float], leg_a: dict[str, Any], leg_b: dict[str, Any]) -> float:
    cover = coverage["prob_at_least_one"]
    ev_avg = (leg_a["expected_value"] + leg_b["expected_value"]) / 2
    edge_avg = (leg_a["edge_pp"] + leg_b["edge_pp"]) / 2
    return cover * 100 + max(ev_avg, 0) * 20 + max(edge_avg, 0) * 0.5 + coverage["prob_both_win"] * 15


def build_hedge_pair_candidates(
    *,
    market_scan: list[dict[str, Any]],
    inplay: dict[str, Any],
    home_team: str,
    away_team: str,
    minute: int = 0,
    bankroll: float = 1000.0,
) -> list[dict[str, Any]]:
    """Monta candidatos pareados a partir do scan quantitativo."""
    idx = _index_scan(market_scan)
    candidates: list[dict[str, Any]] = []

    all_templates = list(_PAIR_TEMPLATES)
    all_templates.extend(_build_dynamic_band_pairs(
        idx, prefix="corners", category="corners", name_prefix="Zona escanteios",
    ))
    all_templates.extend(_build_dynamic_band_pairs(
        idx, prefix="cards", category="cards", name_prefix="Zona cartões", min_band=0.5,
    ))

    for tpl in all_templates:
        am, ao = tpl["leg_a"]
        bm, bo = tpl["leg_b"]
        leg_a = _resolve_leg(idx, am, ao)
        leg_b = _resolve_leg(idx, bm, bo)
        if not leg_a or not leg_b:
            continue

        coverage = _coverage_from_inplay(tpl, inplay, leg_a, leg_b)
        if coverage["prob_at_least_one"] < 0.55:
            continue

        stake_a = min(leg_a["suggested_stake_pct"], 2.5)
        stake_b = min(leg_b["suggested_stake_pct"], 2.5)
        total_stake_pct = round(stake_a + stake_b, 2)

        name = tpl["name"]
        if tpl["id"] == "mandante_nao_perde":
            name = f"{home_team} não perde (split)"
        elif tpl["id"] == "visitante_nao_perde":
            name = f"{away_team} não perde (split)"

        candidates.append({
            "id": tpl["id"],
            "name": name,
            "category": tpl.get("_category") or _pair_category(tpl["id"]),
            "leg_a": leg_a,
            "leg_b": leg_b,
            "coverage": coverage,
            "score": round(_score_pair(coverage, leg_a, leg_b), 2),
            "scenario_a": tpl.get("scenario_a", ""),
            "scenario_b": tpl.get("scenario_b", ""),
            "scenario_both": tpl.get("scenario_both", ""),
            "stake_hint_pct": total_stake_pct,
            "stake_hint_value": round(bankroll * total_stake_pct / 100, 2),
            "minute": minute,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:8]


def _select_diverse_pairs(candidates: list[dict[str, Any]], n: int = 2) -> list[dict[str, Any]]:
    """Escolhe pares de categorias diferentes quando possível."""
    if len(candidates) <= n:
        return candidates

    selected: list[dict[str, Any]] = [candidates[0]]
    used_ids = {selected[0]["id"]}
    used_cats = {selected[0].get("category") or _pair_category(selected[0]["id"])}

    for cat_priority in ("corners", "cards", "goals", "h2h", "other"):
        if len(selected) >= n:
            break
        for c in candidates:
            if c["id"] in used_ids:
                continue
            cat = c.get("category") or _pair_category(c["id"])
            if cat == cat_priority and cat not in used_cats:
                selected.append(c)
                used_ids.add(c["id"])
                used_cats.add(cat)
                break

    for c in candidates:
        if len(selected) >= n:
            break
        if c["id"] not in used_ids:
            selected.append(c)
            used_ids.add(c["id"])

    return selected[:n]


def _parse_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _llm_narrate_pairs(
    *,
    candidates: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    minute: int,
    posture: str,
    confidence: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if not settings.openai_api_key or not settings.live_copilot_enabled:
        return [], "LLM desativado — exibindo pares quantitativos."

    slim = []
    for c in candidates[:6]:
        slim.append({
            "id": c["id"],
            "name": c["name"],
            "leg_a": c["leg_a"]["label"],
            "leg_b": c["leg_b"]["label"],
            "odd_a": c["leg_a"]["market_odd"],
            "odd_b": c["leg_b"]["market_odd"],
            "prob_at_least_one_pct": round(c["coverage"]["prob_at_least_one"] * 100, 1),
            "prob_both_lose_pct": round(c["coverage"]["prob_both_lose"] * 100, 1),
            "scenario_a": c["scenario_a"],
            "scenario_b": c["scenario_b"],
            "scenario_both": c["scenario_both"],
        })

    user_msg = (
        f"Jogo: {home_team} x {away_team}, minuto {minute}, postura {posture}. "
        f"Confiança dados: {confidence.get('score') if confidence else 'n/d'}. "
        f"Candidatos: {json.dumps(slim, ensure_ascii=False)}"
    )

    try:
        resp = httpx.post(
            f"{_OPENAI_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "temperature": 0.25,
                "max_tokens": 700,
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = _parse_json(content)
    except Exception as exc:
        return [], f"Fallback quantitativo: {exc}"

    by_id = {c["id"]: c for c in candidates}
    selected: list[dict[str, Any]] = []
    for item in (parsed.get("estrategias") or [])[:2]:
        cid = str(item.get("id") or "")
        base = by_id.get(cid)
        if not base:
            continue
        merged = dict(base)
        merged["titulo"] = str(item.get("titulo") or base["name"])
        merged["resumo"] = str(item.get("resumo") or "")
        merged["stake_split"] = str(item.get("stake_split") or "50% / 50%")
        merged["cenario_chave"] = str(item.get("cenario_chave") or base.get("scenario_both") or "")
        merged["llm_enriched"] = True
        selected.append(merged)

    return selected, None


def _deterministic_top2(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in _select_diverse_pairs(candidates, n=2):
        item = dict(c)
        item["titulo"] = c["name"]
        item["resumo"] = (
            f"Cobertura estimada {c['coverage']['prob_at_least_one'] * 100:.0f}% — "
            f"{c['scenario_a']}. {c['scenario_b']}."
        )
        item["stake_split"] = "50% / 50% da stake planejada"
        item["cenario_chave"] = c.get("scenario_both") or c.get("scenario_a", "")
        item["llm_enriched"] = False
        out.append(item)
    return out


def build_hedge_pair_strategies(
    *,
    market_scan: list[dict[str, Any]],
    inplay: dict[str, Any],
    home_team: str,
    away_team: str,
    minute: int = 0,
    bankroll: float = 1000.0,
    posture: str = "neutro",
    confidence: dict[str, Any] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Retorna até 2 estratégias pareadas de blindagem."""
    candidates = build_hedge_pair_candidates(
        market_scan=market_scan,
        inplay=inplay,
        home_team=home_team,
        away_team=away_team,
        minute=minute,
        bankroll=bankroll,
    )

    if not candidates:
        return {
            "enabled": bool(settings.live_copilot_enabled and settings.openai_api_key),
            "available": False,
            "strategies": [],
            "candidate_count": 0,
            "error": "Sem mercados suficientes para montar pares complementares.",
        }

    error = None
    if use_llm and settings.live_copilot_enabled and settings.openai_api_key:
        strategies, error = _llm_narrate_pairs(
            candidates=candidates,
            home_team=home_team,
            away_team=away_team,
            minute=minute,
            posture=posture,
            confidence=confidence,
        )
        if len(strategies) < 2:
            strategies = _deterministic_top2(candidates)
    else:
        strategies = _deterministic_top2(candidates)
        if not use_llm:
            error = "Modo rápido — narrativa LLM omitida."

    # Garante diversidade mesmo após LLM
    if len(strategies) >= 2:
        ids = [s["id"] for s in strategies]
        cats = {_pair_category(s["id"]) for s in strategies}
        if len(cats) == 1:
            for alt in candidates:
                if alt["id"] not in ids and _pair_category(alt["id"]) != next(iter(cats)):
                    strategies[1] = dict(alt)
                    strategies[1]["titulo"] = alt["name"]
                    strategies[1]["resumo"] = (
                        f"Cobertura estimada {alt['coverage']['prob_at_least_one'] * 100:.0f}% — "
                        f"{alt['scenario_a']}. {alt['scenario_b']}."
                    )
                    strategies[1]["stake_split"] = "50% / 50% da stake planejada"
                    strategies[1]["cenario_chave"] = alt.get("scenario_both") or alt.get("scenario_a", "")
                    strategies[1]["llm_enriched"] = strategies[1].get("llm_enriched", False)
                    break

    return {
        "enabled": bool(settings.live_copilot_enabled and settings.openai_api_key),
        "available": len(strategies) > 0,
        "strategies": strategies,
        "candidate_count": len(candidates),
        "error": error,
    }
