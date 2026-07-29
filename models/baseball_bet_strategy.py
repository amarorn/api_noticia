"""Plano operacional in-play beisebol (posture, shields, watch list)."""
from __future__ import annotations

from typing import Any

from config import settings
from ingest.superbet.parser import SuperbetEventSnapshot
from models.baseball_dead_market import list_dead_market_flags
from models.baseball_game_phase import BaseballGamePhase


def _tier(edge_pp: float) -> str:
    min_pp = settings.baseball_live_min_edge_pp
    if edge_pp >= min_pp * 2.5:
        return "forte"
    if edge_pp >= min_pp * 1.5:
        return "moderada"
    if edge_pp >= min_pp:
        return "leve"
    return "abaixo_limiar"


def _posture(
    *,
    game_phase: BaseballGamePhase,
    strong_ops: int,
    has_apostar: bool,
) -> str:
    if game_phase.phase == "finished":
        return "defensivo"
    if game_phase.phase == "extras" and not has_apostar:
        return "defensivo"
    if game_phase.block_new_ft_aportes:
        return "defensivo"
    if strong_ops >= 2 and game_phase.phase in {"f5_open", "mid"}:
        return "atacar"
    if strong_ops >= 1:
        return "neutro"
    return "neutro"


def _shields(
    *,
    game_phase: BaseballGamePhase,
    dead_flags: list[str],
    benchmark: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    shields: list[dict[str, Any]] = []

    if game_phase.block_f5:
        shields.append({
            "action": "aguardar",
            "priority": "media",
            "title": "F5 encerrado",
            "reason": "Mercados Entradas 1–5 não aceitam mais apostas após a 5ª entrada.",
        })

    if game_phase.phase == "extras":
        shields.append({
            "action": "cautela",
            "priority": "alta",
            "title": "Entradas extras",
            "reason": (
                "Placar empatado ou jogo prolongado — total FT e corrida N ficam mais voláteis; "
                "reduza stake ou aguarde linha."
            ),
        })

    if game_phase.block_new_ft_aportes and game_phase.run_gap >= 5:
        shields.append({
            "action": "evitar",
            "priority": "alta",
            "title": "Jogo decidido",
            "reason": (
                f"Diferença de {game_phase.run_gap} runs na entrada {game_phase.label} — "
                "evite run line/total FT agressivo no underdog."
            ),
        })

    for reason in dead_flags[:4]:
        shields.append({
            "action": "evitar",
            "priority": "alta",
            "title": "Mercado morto",
            "reason": reason,
        })

    ml = (benchmark or {}).get("moneyline") or {}
    edges = [abs(v.get("edge") or 0) for v in ml.values()]
    if edges and max(edges) > 0.12:
        shields.append({
            "action": "validar",
            "priority": "media",
            "title": "Divergência ML",
            "reason": "Modelo e mercado divergem forte no vencedor — confira feed antes de apostar.",
        })

    return shields


def _wait_reason(
    *,
    game_phase: BaseballGamePhase,
    posture: str,
    opportunities: list[dict[str, Any]],
) -> str | None:
    if game_phase.phase == "finished":
        return "Jogo encerrado."
    if posture == "defensivo" and not opportunities:
        if game_phase.phase == "extras":
            return "Entradas extras possíveis — aguardar linha estável no total FT ou ML."
        if game_phase.block_new_ft_aportes:
            return "Cenário de jogo decidido — priorize cash-out ou monitoramento."
        return "Sem edge suficiente no momento."
    if posture == "neutro" and not any(o.get("tier") in {"forte", "moderada"} for o in opportunities):
        return "Edge positivo fraco — aguardar melhor linha ou confirmação na próxima entrada."
    return None


def build_baseball_bet_strategy_report(
    *,
    inplay: Any,
    snapshot: SuperbetEventSnapshot,
    aportes: list[dict[str, Any]],
    game_phase: BaseballGamePhase,
    benchmark: dict[str, Any] | None = None,
    baseball_innings: list[dict[str, int]] | None = None,
) -> dict[str, Any]:
    """Relatório operacional espelhando wc_bet_strategy (versão beisebol)."""
    filtered: list[dict[str, Any]] = []
    for a in aportes:
        from models.baseball_dead_market import is_dead_baseball_market

        dead, _ = is_dead_baseball_market(
            a.get("market", ""),
            a.get("outcome", ""),
            home_score=inplay.home_score,
            away_score=inplay.away_score,
            inning=inplay.inning,
            baseball_innings=baseball_innings,
        )
        if dead:
            continue
        if game_phase.block_f5 and a.get("market", "").startswith("f5_"):
            continue
        if game_phase.block_ft_totals and a.get("market") == "total_runs":
            continue
        filtered.append(a)

    opportunities: list[dict[str, Any]] = []
    for a in filtered[:8]:
        tier = _tier(float(a.get("edge_pp") or 0))
        opportunities.append({
            **a,
            "tier": tier,
            "timing": game_phase.label,
        })

    strong = sum(1 for o in opportunities if o.get("tier") in {"forte", "moderada"})
    has_apostar = any(o.get("action") == "apostar" for o in opportunities)
    posture = _posture(game_phase=game_phase, strong_ops=strong, has_apostar=has_apostar)

    dead_flags = list_dead_market_flags(
        aportes,
        home_score=inplay.home_score,
        away_score=inplay.away_score,
        inning=inplay.inning,
        baseball_innings=baseball_innings,
    )
    shields = _shields(game_phase=game_phase, dead_flags=dead_flags, benchmark=benchmark)

    watch_list = sorted(
        [a for a in aportes if float(a.get("edge_pp") or 0) >= 3.0],
        key=lambda x: float(x.get("edge_pp") or 0),
        reverse=True,
    )[:5]

    market_scan: list[dict[str, Any]] = []
    for section, key in (("moneyline", "moneyline"), ("totals", "totals"), ("spread", "spread")):
        block = (benchmark or {}).get(key) or {}
        for line_id, row in block.items():
            edge = row.get("edge") or row.get("edge_over") or row.get("edge_home")
            if edge is None:
                continue
            market_scan.append({
                "category": section,
                "line": str(line_id),
                "edge_pp": round(float(edge) * 100, 2),
                "model": row.get("model") or row.get("model_over") or row.get("model_home_cover"),
                "market": row.get("market") or row.get("market_over") or row.get("market_home_cover"),
            })
    market_scan.sort(key=lambda x: abs(x["edge_pp"]), reverse=True)

    return {
        "posture": posture,
        "wait_reason": _wait_reason(
            game_phase=game_phase,
            posture=posture,
            opportunities=opportunities,
        ),
        "opportunities": opportunities,
        "shields": shields,
        "watch_list": watch_list,
        "market_scan": market_scan[:12],
        "rules": [
            "F5 válido apenas até o fim da 5ª entrada.",
            "Total FT cauteloso a partir da 8ª entrada ou em extras.",
            "Under morto quando runs no placar já ultrapassaram a linha.",
            "Stake Kelly limitada pelo teto global de banca.",
        ],
    }
