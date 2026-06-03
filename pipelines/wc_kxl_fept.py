"""Helpers FEPT/FECL alinhados ao PDF KXL."""

from __future__ import annotations

from schemas.wc_kxl_dynamic import (
    FeclAmbiente,
    FeptEscalacao,
    FeptJogador,
    FeptTitularesEstruturados,
)

WET_GRAMADO = frozenset({"molhado", "ruim", "encharcado", "pesado"})
SYNTH_GRAMADO = frozenset({"sintetico", "sintético", "artificial"})
SCHEME_ATTACK = frozenset({"4-2-3-1", "4-3-3", "3-4-3", "4-2-4"})
SCHEME_DEFENSIVE = frozenset({"5-3-2", "5-4-1", "3-5-2", "4-5-1", "4-1-4-1"})


def fecl_is_wet(fecl: FeclAmbiente) -> bool:
    if fecl.previsao_chuva_pct is not None and fecl.previsao_chuva_pct >= 40.0:
        return True
    if fecl.chuva_mm is not None and fecl.chuva_mm >= 3.0:
        return True
    if fecl.umidade_pct is not None and fecl.umidade_pct >= 85.0:
        return True
    estado = (fecl.estado_gramado or fecl.gramado or "").strip().lower()
    return estado in WET_GRAMADO


def fecl_is_synthetic(fecl: FeclAmbiente) -> bool:
    estado = (fecl.estado_gramado or fecl.gramado or "").strip().lower()
    return estado in SYNTH_GRAMADO or "sint" in estado


def scheme_modifiers(esquema: str | None) -> tuple[float, float, str]:
    if not esquema:
        return 1.0, 1.0, ""
    key = esquema.strip().lower().replace(" ", "")
    if key in {s.replace(" ", "") for s in SCHEME_ATTACK}:
        return 1.06, 0.97, f"esquema ofensivo ({esquema})"
    if key in {s.replace(" ", "") for s in SCHEME_DEFENSIVE}:
        return 0.94, 1.05, f"esquema retrancado ({esquema})"
    return 1.0, 1.0, ""


def _as_player(raw: dict | FeptJogador, linha: str) -> FeptJogador | None:
    if isinstance(raw, FeptJogador):
        if raw.linha:
            return raw
        return raw.model_copy(update={"linha": linha})
    return _player_from_dict(raw, linha)


def _player_from_dict(data: dict, linha: str) -> FeptJogador | None:
    nome = data.get("nome") or data.get("name")
    if not nome:
        return None
    nota = data.get("nota_sofascore") or data.get("nota")
    return FeptJogador(
        nome=str(nome),
        posicao=data.get("posicao"),
        nota_sofascore=float(nota) if nota is not None else None,
        linha=linha,
    )


def flatten_titulares_estruturados(block: FeptTitularesEstruturados) -> list[FeptJogador]:
    out: list[FeptJogador] = []
    if block.goleiro:
        p = _as_player(block.goleiro, "goleiro")
        if p:
            out.append(p)
    for j in block.defensores:
        p = _as_player(j, "defesa")
        if p:
            out.append(p)
    for j in block.meio_campistas:
        p = _as_player(j, "meio")
        if p:
            out.append(p)
    for j in block.atacantes:
        p = _as_player(j, "ataque")
        if p:
            out.append(p)
    for j in block.defesa_extra:
        p = _as_player(j, "defesa")
        if p:
            out.append(p)
    return out


def fept_players_for_side(fept: FeptEscalacao, is_home: bool) -> list[FeptJogador]:
    if is_home:
        if fept.mandante_titulares_notas:
            return flatten_titulares_estruturados(fept.mandante_titulares_notas)
        return list(fept.titulares_mandante)
    if fept.visitante_titulares_notas:
        return flatten_titulares_estruturados(fept.visitante_titulares_notas)
    return list(fept.titulares_visitante)


def fept_esquema(fept: FeptEscalacao, is_home: bool) -> str | None:
    return fept.esquema_mandante if is_home else fept.esquema_visitante


def weighted_squad_energy(players: list[FeptJogador]) -> float | None:
    weights = {"goleiro": 0.08, "defesa": 0.32, "meio": 0.30, "ataque": 0.30}
    buckets: dict[str, list[float]] = {k: [] for k in weights}
    for p in players:
        if p.nota_sofascore is None:
            continue
        linha = (p.linha or "meio").strip().lower()
        if linha not in buckets:
            linha = "meio"
        buckets[linha].append(p.nota_sofascore)
    if not any(buckets.values()):
        return None
    total = 0.0
    for linha, w in weights.items():
        if buckets[linha]:
            total += w * (sum(buckets[linha]) / len(buckets[linha]))
        else:
            total += w * 6.5
    return max(0.5, min(1.35, total / 7.5))
