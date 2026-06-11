"""Recomendações de cash-out e aporte com base no modelo in-play vs mercado."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from config import settings
from models.economics import coase_effective_min_edge, live_effective_min_edge
from models.ev_value import evaluate_outcome
from models.wc_trend_confidence import assess_prediction_confidence
from ingest.superbet.parser import SuperbetEventSnapshot


@dataclass
class PickInputData:
    """Um palpite individual dentro de uma simples ou múltipla."""
    market: str
    outcome: str
    target_value: str | None = None


@dataclass
class UserBetInput:
    market: str
    outcome: str
    stake: float
    odds_placed: float
    picks: list[PickInputData] = field(default_factory=list)
    target_value: str | None = None


@dataclass
class CashoutAdvice:
    action: str
    confidence: float
    reason: str
    current_model_prob: float
    placed_implied_prob: float
    remaining_ev: float
    estimated_fair_cashout: float
    potential_return: float


@dataclass
class AporteAdvice:
    market: str
    outcome: str
    label: str
    model_prob: float
    market_odd: float
    implied_prob: float
    expected_value: float
    edge_pp: float
    kelly_quarter: float
    suggested_stake_pct: float
    action: str


def _prob_from_inplay(inplay: dict[str, Any], market: str, outcome: str) -> float | None:
    key = f"{market}:{outcome}".lower()
    flp = inplay.get("final_line_probs", {})
    team_lp = inplay.get("team_final_line_probs", {})
    sh_lp = inplay.get("second_half_line_probs", {})
    ht_lp = inplay.get("ht_line_probs", {})
    mapping: dict[str, float] = {
        "h2h:1": inplay.get("prob_final_home", 0),
        "h2h:x": inplay.get("prob_final_draw", 0),
        "h2h:2": inplay.get("prob_final_away", 0),
        "h2h:0": inplay.get("prob_final_draw", 0),
        "next_goal:home": inplay.get("prob_next_goal_home", 0),
        "next_goal:away": inplay.get("prob_next_goal_away", 0),
        "next_goal:none": inplay.get("prob_no_more_goals", 0),
        "btts:yes": inplay.get("btts_final", 0),
        "btts:no": 1.0 - float(inplay.get("btts_final", 0)),
        "over_1_5:yes": flp.get("over_1_5", 0),
        "over_1_5:no": flp.get("under_1_5", 0),
        "over_2_5:yes": flp.get("over_2_5", 0),
        "over_2_5:no": flp.get("under_2_5", 0),
        "over_3_5:yes": flp.get("over_3_5", 0),
        "over_3_5:no": flp.get("under_3_5", 0),
        "over_4_5:yes": flp.get("over_4_5", 0),
        "over_4_5:no": flp.get("under_4_5", 0),
        "combo_btts_over_2_5:yes": inplay.get("combo_markets", {}).get("btts_and_over_2_5", 0),
        "combo_btts_over_2_5:no": 1.0 - float(inplay.get("combo_markets", {}).get("btts_and_over_2_5", 0)),
        "combo_btts_over_3_5:yes": inplay.get("combo_markets", {}).get("btts_and_over_3_5", 0),
        "combo_btts_over_3_5:no": 1.0 - float(inplay.get("combo_markets", {}).get("btts_and_over_3_5", 0)),
        "combo_home_btts:yes": inplay.get("combo_markets", {}).get("ft_home_and_btts", 0),
        "combo_away_btts:yes": inplay.get("combo_markets", {}).get("ft_away_and_btts", 0),
        "home_over_0_5:yes": team_lp.get("home_over_0_5", 0),
        "home_over_1_5:yes": team_lp.get("home_over_1_5", 0),
        "home_over_2_5:yes": team_lp.get("home_over_2_5", 0),
        "away_over_0_5:yes": team_lp.get("away_over_0_5", 0),
        "away_over_1_5:yes": team_lp.get("away_over_1_5", 0),
        "away_over_2_5:yes": team_lp.get("away_over_2_5", 0),
        "2h_over_0_5:yes": sh_lp.get("over_0_5", 0),
        "2h_over_1_5:yes": sh_lp.get("over_1_5", 0),
        "2h_over_0_5:no": sh_lp.get("under_0_5", 0),
        "1h_over_0_5:yes": ht_lp.get("over_0_5", 0),
        "1h_over_1_5:yes": ht_lp.get("over_1_5", 0),
    }
    if key in mapping:
        return float(mapping[key])
    combo = inplay.get("combo_markets", {})
    if market in combo and outcome in {"yes", "sim"}:
        return float(combo[market])
    return None


def _effective_min_edge(*, min_edge: float | None, live: bool) -> float:
    if live:
        return live_effective_min_edge(min_edge)
    return coase_effective_min_edge(min_edge or settings.ev_min_edge)


def _house_prob(snapshot: SuperbetEventSnapshot | None, market: str, outcome: str) -> float | None:
    """Retorna a generosity_prob (prob real da casa sem margem) se disponível."""
    if snapshot is None or market != "h2h":
        return None
    mapping = {"1": "home", "2": "away"}
    key = mapping.get(outcome)
    if key is None:
        return None
    return snapshot.generosity_probs.get(key)


def _market_odd(snapshot: SuperbetEventSnapshot | None, market: str, outcome: str) -> float | None:
    if snapshot is None:
        return None
    out = outcome.upper()
    if market == "h2h":
        key = "X" if out in {"X", "0", "DRAW", "EMPATE"} else out
        return snapshot.h2h_odds.get(key)
    if market.startswith("over_"):
        line = market.replace("over_", "").replace("_", ".")
        prices = snapshot.totals.get(line) or {}
        for name, price in prices.items():
            if outcome in {"yes", "sim"} and "mais" in name.lower():
                return price
            if outcome in {"no", "não", "nao"} and "menos" in name.lower():
                return price
    if market == "btts":
        key = "yes" if outcome.lower() in {"yes", "sim"} else "no"
        return (snapshot.btts_odds or {}).get(key)
    if market == "next_goal":
        return (snapshot.next_goal_odds or {}).get(outcome.lower())
    # --- Total por time (home_over_X_Y, away_over_X_Y) ---
    if market.startswith(("home_over_", "away_over_")):
        team_totals = getattr(snapshot, "team_totals", None) or {}
        side = "home" if market.startswith("home_") else "away"
        line = market.replace(f"{side}_over_", "").replace("_", ".")
        prices = team_totals.get(side, {}).get(line, {})
        for name, price in prices.items():
            if "mais" in name.lower():
                return price
        return None
    # --- 2º Tempo / 1º Tempo totals ---
    if market.startswith("2h_over_"):
        sh_totals = getattr(snapshot, "second_half_totals", None) or {}
        line = market.replace("2h_over_", "").replace("_", ".")
        prices = sh_totals.get(line, {})
        for name, price in prices.items():
            if outcome in {"yes", "sim"} and "mais" in name.lower():
                return price
            if outcome in {"no", "não", "nao"} and "menos" in name.lower():
                return price
        return None
    if market.startswith("1h_over_"):
        ht_totals = getattr(snapshot, "first_half_totals", None) or {}
        line = market.replace("1h_over_", "").replace("_", ".")
        prices = ht_totals.get(line, {})
        for name, price in prices.items():
            if "mais" in name.lower():
                return price
        return None
    # --- Combos (extraídos do parser) ---
    if market.startswith("combo_"):
        combo_key_map = {
            "combo_btts_over_2_5": "btts_and_over_2_5",
            "combo_btts_over_3_5": "btts_and_over_3_5",
            "combo_home_btts": "ft_and_btts",
            "combo_away_btts": "ft_and_btts",
        }
        combo_key = combo_key_map.get(market)
        if not combo_key:
            return None
        combo_odds = snapshot.combo_markets.get(combo_key, {})
        if not combo_odds:
            return None
        # Para ft_and_btts, precisa achar a sub-odd correta
        if market == "combo_home_btts":
            for label_name, price in combo_odds.items():
                if "1" in label_name.split("/")[0] if "/" in label_name else "1" in label_name:
                    return price
            # Fallback: menor odd (mais provável)
            return min(combo_odds.values()) if combo_odds else None
        if market == "combo_away_btts":
            for label_name, price in combo_odds.items():
                if "2" in label_name:
                    return price
            return None
        # combo_btts_over: geralmente "Sim" é a aposta
        for label_name, price in combo_odds.items():
            if "sim" in label_name.lower() or "yes" in label_name.lower():
                return price
        # Se não tem "sim", pegar a primeira
        return next(iter(combo_odds.values()), None)
    return None


def advise_cashout(
    bet: UserBetInput,
    inplay: dict[str, Any],
    *,
    minute: int = 0,
    book_margin: float = 0.08,
) -> CashoutAdvice:
    current_p = _prob_from_inplay(inplay, bet.market, bet.outcome)
    if current_p is None:
        return CashoutAdvice(
            action="aguardar",
            confidence=0.0,
            reason="Mercado da aposta não mapeado no modelo in-play.",
            current_model_prob=0.0,
            placed_implied_prob=0.0,
            remaining_ev=0.0,
            estimated_fair_cashout=bet.stake,
            potential_return=bet.stake * bet.odds_placed,
        )

    placed_implied = 1.0 / max(bet.odds_placed, 1.01)
    remaining_ev = current_p * bet.odds_placed - 1.0
    potential = bet.stake * bet.odds_placed
    estimated_fair = bet.stake * (1.0 + (bet.odds_placed - 1.0) * current_p) * (1.0 - book_margin)

    prob_ratio = current_p / max(placed_implied, 1e-6)
    late_game = minute >= 80

    if remaining_ev < -0.10 or prob_ratio < 0.65:
        action = "cashout"
        reason = (
            "O modelo indica que a chance de ganhar caiu bastante em relação à odd que você pegou. "
            "Cash-out protege o que ainda resta de valor."
        )
        confidence = min(0.95, 0.7 + abs(remaining_ev))
    elif remaining_ev < -0.04 or (prob_ratio < 0.80 and late_game):
        action = "cashout_parcial"
        reason = (
            "EV residual negativo ou jogo avançado com probabilidade abaixo da entrada. "
            "Considere cash-out parcial (50–70% do valor oferecido)."
        )
        confidence = 0.65
    elif remaining_ev > 0.06 and prob_ratio > 1.05:
        action = "manter"
        reason = (
            "O modelo ainda vê valor na sua aposta em relação à odd de entrada. "
            "Não há sinal forte para cash-out."
        )
        confidence = min(0.9, 0.55 + remaining_ev)
    else:
        action = "aguardar"
        reason = (
            "Cenário neutro: nem proteção urgente nem valor claro para dobrar. "
            "Monitore a cada 3–5 minutos."
        )
        confidence = 0.5

    return CashoutAdvice(
        action=action,
        confidence=round(confidence, 3),
        reason=reason,
        current_model_prob=round(current_p, 4),
        placed_implied_prob=round(placed_implied, 4),
        remaining_ev=round(remaining_ev, 4),
        estimated_fair_cashout=round(estimated_fair, 2),
        potential_return=round(potential, 2),
    )


def _is_comeback_unrealistic(
    outcome: str,
    home_score: int,
    away_score: int,
    *,
    deficit_threshold: int = 3,
) -> bool:
    """Filtro de sanidade: viradas de 3+ gols de déficit são irrealistas.

    O modelo Poisson superestima probabilidades de viradas extremas porque
    distribui massa residual em cenários praticamente impossíveis.
    Retorna True se o resultado H2H requer virada irrealista.
    """
    deficit = home_score - away_score  # positivo = casa lidera
    if outcome == "2" and deficit >= deficit_threshold:
        # Fora precisa virar 3+ gols — irrealista
        return True
    if outcome == "1" and -deficit >= deficit_threshold:
        # Casa precisa virar 3+ gols — irrealista
        return True
    return False


def _generosity_blocks(
    snapshot: SuperbetEventSnapshot, market: str, outcome: str
) -> bool:
    """Verifica se a generosity da Superbet é tão baixa que bloqueia a recomendação.

    Se a Superbet dá <5% de chance para o outcome (via generosity_probs),
    o modelo não deve recomendar essa aposta — a casa tem dados que não temos.
    """
    gen = getattr(snapshot, "generosity_probs", None) or {}
    if not gen:
        return False

    BLOCK_THRESHOLD = 0.05  # 5%

    if market == "h2h":
        if outcome == "1" and gen.get("home", 1.0) < BLOCK_THRESHOLD:
            return True
        if outcome == "2" and gen.get("away", 1.0) < BLOCK_THRESHOLD:
            return True
        if outcome == "X" and gen.get("draw", 1.0) < BLOCK_THRESHOLD:
            return True
    elif market == "next_goal":
        if outcome == "home" and gen.get("home", 1.0) < BLOCK_THRESHOLD:
            return True
        if outcome == "away" and gen.get("away", 1.0) < BLOCK_THRESHOLD:
            return True
    return False


def _aporte_candidates(
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    home_team: str = "Casa",
    away_team: str = "Fora",
    home_score: int | None = None,
    away_score: int | None = None,
) -> list[tuple[str, str, str, float, float]]:
    """market, outcome, label, model_prob, market_odd"""
    candidates: list[tuple[str, str, str, float, float]] = []

    # Extrair placar do inplay se não passado explicitamente
    if home_score is None or away_score is None:
        score_str = inplay.get("current_score", "0x0")
        parts = str(score_str).split("x")
        home_score = int(parts[0]) if len(parts) == 2 else 0
        away_score = int(parts[1]) if len(parts) == 2 else 0

    flp = inplay.get("final_line_probs", {})
    team_lp = inplay.get("team_final_line_probs", {})
    sh_lp = inplay.get("second_half_line_probs", {})
    ht_lp = inplay.get("ht_line_probs", {})
    combos = inplay.get("combo_markets", {})

    specs: list[tuple[str, str, str, Callable[[], float | None]]] = [
        # --- 1X2 ---
        ("h2h", "1", f"{home_team} vence", lambda: inplay.get("prob_final_home")),
        ("h2h", "X", "Empate", lambda: inplay.get("prob_final_draw")),
        ("h2h", "2", f"{away_team} vence", lambda: inplay.get("prob_final_away")),
        # --- BTTS ---
        ("btts", "yes", "Ambos marcam", lambda: inplay.get("btts_final")),
        ("btts", "no", "Ambos não marcam", lambda: (
            1.0 - inplay["btts_final"] if "btts_final" in inplay else None
        )),
        # --- Próximo gol ---
        ("next_goal", "home", f"Próximo gol {home_team}", lambda: inplay.get("prob_next_goal_home")),
        ("next_goal", "away", f"Próximo gol {away_team}", lambda: inplay.get("prob_next_goal_away")),
    ]

    # --- Total de Gols (linhas disponíveis no snapshot) ---
    if snapshot:
        for line_key in snapshot.totals:
            line_num = line_key.replace(".", "_")
            over_prob = flp.get(f"over_{line_num}")
            under_prob = flp.get(f"under_{line_num}")
            if over_prob is not None:
                specs.append((f"over_{line_num}", "yes", f"Mais de {line_key} gols", lambda p=over_prob: p))
            if under_prob is not None:
                specs.append((f"over_{line_num}", "no", f"Menos de {line_key} gols", lambda p=under_prob: p))

    # --- Total por Time (linhas disponíveis) ---
    if snapshot:
        for side in ("home", "away"):
            team_name = home_team if side == "home" else away_team
            for line_key in snapshot.team_totals.get(side, {}):
                line_num = line_key.replace(".", "_")
                prob = team_lp.get(f"{side}_over_{line_num}")
                if prob is not None:
                    specs.append((f"{side}_over_{line_num}", "yes", f"{team_name} mais de {line_key} gols", lambda p=prob: p))

    # --- 2º Tempo (linhas disponíveis) ---
    if snapshot:
        for line_key in snapshot.second_half_totals:
            line_num = line_key.replace(".", "_")
            over_prob = sh_lp.get(f"over_{line_num}")
            under_prob = sh_lp.get(f"under_{line_num}")
            if over_prob is not None:
                specs.append((f"2h_over_{line_num}", "yes", f"2º Tempo: mais de {line_key} gols", lambda p=over_prob: p))
            if under_prob is not None:
                specs.append((f"2h_over_{line_num}", "no", f"2º Tempo: menos de {line_key} gols", lambda p=under_prob: p))

    # --- 1º Tempo (linhas disponíveis) ---
    if snapshot:
        for line_key in snapshot.first_half_totals:
            line_num = line_key.replace(".", "_")
            over_prob = ht_lp.get(f"over_{line_num}")
            under_prob = ht_lp.get(f"under_{line_num}")
            if over_prob is not None:
                specs.append((f"1h_over_{line_num}", "yes", f"1º Tempo: mais de {line_key} gols", lambda p=over_prob: p))
            if under_prob is not None:
                specs.append((f"1h_over_{line_num}", "no", f"1º Tempo: menos de {line_key} gols", lambda p=under_prob: p))

    # --- Combos ---
    combo_map = {
        "combo_btts_over_2_5": ("btts_and_over_2_5", "BTTS + Mais de 2.5"),
        "combo_btts_over_3_5": ("btts_and_over_3_5", "BTTS + Mais de 3.5"),
        "combo_home_btts": ("ft_home_and_btts", f"{home_team} vence + BTTS"),
        "combo_away_btts": ("ft_away_and_btts", f"{away_team} vence + BTTS"),
    }
    for market, (combo_key, label) in combo_map.items():
        prob = combos.get(combo_key)
        if prob is not None:
            specs.append((market, "yes", label, lambda p=prob: p))
    for market, outcome, label, prob_fn in specs:
        prob = prob_fn()
        if prob is None or prob <= 0:
            continue
        # Filtro de sanidade: não recomendar viradas de 3+ gols
        if market == "h2h" and _is_comeback_unrealistic(
            outcome, home_score, away_score
        ):
            continue
        # ── Gate: não apostar next_goal no time que está apanhando (gap >= 2) ──
        score_gap = home_score - away_score
        if market == "next_goal" and outcome == "away" and score_gap >= 2:
            continue  # time visitante perdendo por 2+ → não apostar nele
        if market == "next_goal" and outcome == "home" and score_gap <= -2:
            continue  # time mandante perdendo por 2+ → não apostar nele
        # ── Gate: se generosity da Superbet < 5% para o outcome, bloquear ──
        if snapshot and _generosity_blocks(snapshot, market, outcome):
            continue
        odd = _market_odd(snapshot, market, outcome)
        if odd is None or odd <= 1.0:
            continue
        # ── Guarda: odd mínima (não recomendar odds muito baixas) ──
        if odd < settings.live_min_market_odd:
            continue
        # ── Guarda: divergência absurda modelo vs mercado (modelo errado) ──
        if odd > 10.0 and prob < 0.20:
            # Modelo diz <20% mas odd sugere <10% → modelo provavelmente errado
            continue
        if odd > 20.0:
            # Odds > 20 = mercado morto, não recomendar
            continue
        candidates.append((market, outcome, label, float(prob), float(odd)))
    return candidates


def scan_all_market_edges(
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    bankroll: float | None = None,
    min_edge: float | None = None,
    live: bool = False,
    home_team: str = "Casa",
    away_team: str = "Fora",
    minute: int = 0,
) -> tuple[list[dict[str, Any]], float]:
    """Todos os mercados mapeados com EV, ordenados do maior para o menor."""
    threshold = _effective_min_edge(min_edge=min_edge, live=live)
    # Ajuste de fim de jogo
    effective_threshold = threshold
    if minute > settings.live_max_minute_full_advice:
        effective_threshold = threshold * settings.live_late_game_ev_multiplier
    bankroll = bankroll or 1000.0

    # ── Gate: jogo morto (score gap ≥ 3 E minute > 50) → sem recomendações ──
    score_str = inplay.get("current_score", "0x0")
    parts = str(score_str).split("x")
    h_sc = int(parts[0]) if len(parts) == 2 and parts[0].isdigit() else 0
    a_sc = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
    gap = abs(h_sc - a_sc)
    if gap >= 3 and minute > 50:
        # Jogo decidido — não recomendar nada
        return [], effective_threshold

    rows: list[dict[str, Any]] = []

    for market, outcome, label, prob, odd in _aporte_candidates(
        inplay, snapshot, home_team=home_team, away_team=away_team,
    ):
        hp = _house_prob(snapshot, market, outcome)
        ev = evaluate_outcome(outcome, prob, odd, house_prob=hp)
        edge_pp = (prob - ev.implied_prob) * 100
        kelly_q = ev.kelly_quarter
        suggested_pct = round(min(5.0, kelly_q * 100), 2)
        # Verificação de qualidade: edge em pp + threshold efetivo
        quality_pass = (
            ev.expected_value >= effective_threshold
            and edge_pp >= settings.live_min_edge_pp
        )
        rows.append({
            "market": market,
            "outcome": outcome,
            "label": label,
            "model_prob": round(prob, 4),
            "market_odd": round(odd, 3),
            "implied_prob": round(ev.implied_prob, 4),
            "expected_value": round(ev.expected_value, 4),
            "edge_pp": round(edge_pp, 2),
            "suggested_stake_pct": suggested_pct,
            "suggested_stake_value": round(bankroll * suggested_pct / 100, 2),
            "meets_threshold": quality_pass,
        })

    rows.sort(key=lambda x: x["expected_value"], reverse=True)
    return rows, effective_threshold


def _is_suspicious_odd(
    prob: float,
    odd: float,
    *,
    house_prob: float | None = None,
    max_fair_odd_multiplier: float = 3.0,
) -> bool:
    """Detecta odds suspeitas que provavelmente estão desatualizadas.

    Se `house_prob` estiver disponível (prob real da casa sem margem), compara
    a odd vs odd justa da casa em vez da justa do modelo — é muito mais preciso
    para detectar odds obsoletas (ex: mercado já fechou e sobra uma odd alta)
    porque a casa já removeu a margem e calculou probabilidades.
    """
    if prob <= 0:
        return True
    if house_prob is not None and house_prob > 0:
        fair_odd = 1.0 / house_prob
    else:
        fair_odd = 1.0 / prob
    return odd > fair_odd * max_fair_odd_multiplier


def advise_aportes(
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    bankroll: float | None = None,
    min_edge: float | None = None,
    max_recommendations: int = 5,
    live: bool = False,
    home_team: str = "Casa",
    away_team: str = "Fora",
    allow_h2h: bool = True,
    minute: int = 0,
) -> list[AporteAdvice]:
    threshold = _effective_min_edge(min_edge=min_edge, live=live)
    # ── Guarda de fim de jogo: exigir EV muito maior após minuto 85 ──
    if minute > settings.live_max_minute_full_advice:
        threshold *= settings.live_late_game_ev_multiplier
    bankroll = bankroll or 1000.0
    out: list[AporteAdvice] = []

    for market, outcome, label, prob, odd in _aporte_candidates(
        inplay, snapshot, home_team=home_team, away_team=away_team,
    ):
        # Filtro de confiança: sem dados suficientes, não recomendar H2H
        if market == "h2h" and not allow_h2h:
            continue
        # Filtro de sanidade: odds suspeitas (provavelmente desatualizadas)
        hp = _house_prob(snapshot, market, outcome)
        if _is_suspicious_odd(prob, odd, house_prob=hp):
            continue
        ev = evaluate_outcome(outcome, prob, odd, house_prob=hp)
        edge_pp = (prob - ev.implied_prob) * 100
        # ── Guarda de edge mínimo em pp: EV% não basta, precisa edge real ──
        if edge_pp < settings.live_min_edge_pp:
            continue
        if ev.expected_value < threshold:
            continue
        kelly_q = ev.kelly_quarter
        suggested_pct = round(min(5.0, kelly_q * 100), 2)
        action = "aportar" if ev.expected_value >= threshold * 2 else "aportar_pequeno"
        out.append(
            AporteAdvice(
                market=market,
                outcome=outcome,
                label=label,
                model_prob=round(prob, 4),
                market_odd=round(odd, 3),
                implied_prob=round(ev.implied_prob, 4),
                expected_value=round(ev.expected_value, 4),
                edge_pp=round(edge_pp, 2),
                kelly_quarter=round(kelly_q, 4),
                suggested_stake_pct=suggested_pct,
                action=action,
            )
        )

    out.sort(key=lambda x: x.expected_value, reverse=True)
    return out[:max_recommendations]


def build_bet_advice_report(
    *,
    home_team: str,
    away_team: str,
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    user_bet: UserBetInput | None,
    minute: int = 0,
    bankroll: float | None = None,
    features: Any = None,
) -> dict[str, Any]:
    cashout = None
    if user_bet is not None:
        cashout = advise_cashout(user_bet, inplay, minute=minute)

    # Calcular confiança da previsão
    score_parts = str(inplay.get("current_score", "0x0")).split("x")
    home_score = int(score_parts[0]) if len(score_parts) == 2 else 0
    away_score = int(score_parts[1]) if len(score_parts) == 2 else 0
    confidence = assess_prediction_confidence(
        features,
        home_team=home_team,
        away_team=away_team,
        minute=minute,
        home_score=home_score,
        away_score=away_score,
    )

    # Se confiança for baixa, não recomendar apostas H2H
    min_confidence_for_h2h = 0.3
    allow_h2h = confidence.score >= min_confidence_for_h2h

    aportes = advise_aportes(
        inplay,
        snapshot,
        bankroll=bankroll,
        live=True,
        home_team=home_team,
        away_team=away_team,
        allow_h2h=allow_h2h,
        minute=minute,
    )
    return {
        "home_team": home_team,
        "away_team": away_team,
        "minute": minute,
        "current_score": inplay.get("current_score"),
        "confidence": {
            "score": confidence.score,
            "label": confidence.label,
            "reason": confidence.reason,
        },
        "cashout": None if cashout is None else {
            "action": cashout.action,
            "confidence": cashout.confidence,
            "reason": cashout.reason,
            "current_model_prob": cashout.current_model_prob,
            "placed_implied_prob": cashout.placed_implied_prob,
            "remaining_ev": cashout.remaining_ev,
            "estimated_fair_cashout": cashout.estimated_fair_cashout,
            "potential_return": cashout.potential_return,
        },
        "aportes": [
            {
                "market": a.market,
                "outcome": a.outcome,
                "label": a.label,
                "model_prob": a.model_prob,
                "market_odd": a.market_odd,
                "implied_prob": a.implied_prob,
                "expected_value": a.expected_value,
                "edge_pp": a.edge_pp,
                "kelly_quarter": a.kelly_quarter,
                "suggested_stake_pct": a.suggested_stake_pct,
                "suggested_stake_value": round((bankroll or 1000) * a.suggested_stake_pct / 100, 2),
                "action": a.action,
            }
            for a in aportes
        ],
    }
