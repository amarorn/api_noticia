"""Resolve resultado de apostas in-play a partir do placar final/intervalo.

Determina se uma aposta gravada em live_ticks ganhou (True), perdeu (False) ou
não pode ser resolvida com os dados disponíveis (None).

Mercados suportados:
  - h2h / ft_h2h / 1h_h2h / 2h_h2h       → 1X2 por período
  - ft_hcap / 1h_hcap / 2h_hcap           → handicap europeu por período
  - ft_ah / 1h_ah / 2h_ah                 → handicap asiático (linhas quarto)
  - over_X_Y / 1h_over_X_Y / 2h_over_X_Y → total de gols por período
  - home_over_X_Y / away_over_X_Y         → gols por equipe (FT)
  - btts                                   → ambos marcam (FT)
  - combo_btts_over_X_Y                   → BTTS + over FT
  - Xh_cs_A_B                             → placar exato por período
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from models.wc_handicap_score import handicap_line_from_key, parse_any_handicap_market


@dataclass(frozen=True)
class GameResult:
    ft_home: int
    ft_away: int
    ht_home: int | None = None
    ht_away: int | None = None

    @property
    def sh_home(self) -> int | None:
        return (self.ft_home - self.ht_home) if self.ht_home is not None else None

    @property
    def sh_away(self) -> int | None:
        return (self.ft_away - self.ht_away) if self.ht_away is not None else None


def _period_goals(result: GameResult, period: str) -> tuple[int, int] | None:
    """Retorna (home_goals, away_goals) para o período; None se dados insuficientes."""
    if period in ("ft", "h2h"):
        return result.ft_home, result.ft_away
    if period == "1h":
        if result.ht_home is None:
            return None
        return result.ht_home, result.ht_away  # type: ignore[return-value]
    if period == "2h":
        if result.sh_home is None:
            return None
        return result.sh_home, result.sh_away  # type: ignore[return-value]
    return None


def _resolve_h2h(home: int, away: int, outcome: str) -> bool:
    """Resolve resultado 1X2: '1' = casa, 'X' = empate, '2' = fora."""
    if home > away:
        actual = "1"
    elif home == away:
        actual = "X"
    else:
        actual = "2"
    return actual == outcome.upper()


def _resolve_european_handicap(home: int, away: int, side: str, line: float) -> bool | None:
    """Resolve handicap europeu (sem push — linhas com .5).

    `side` = 'home' ou 'away'; `line` é a linha do lado apostado (ex: -0.5, +1.5).
    outcome 'yes' é sempre assumido (a aposta é no time com o handicap).
    """
    if side == "home":
        adjusted = home + line - away
    else:
        adjusted = away + line - home
    if adjusted == 0:
        return None  # push (linhas inteiras apenas)
    return adjusted > 0


def _asian_handicap_result(home: int, away: int, side: str, line: float) -> float:
    """Retorna resultado asiático: +1.0 (ganhou), +0.5 (meio ganhou),
    0.0 (push), -0.5 (meio perdeu), -1.0 (perdeu).

    Linhas quarto (±0.25, ±0.75) são splits de duas linhas adjacentes.
    """
    if side == "home":
        margin = home - away
    else:
        margin = away - home

    adjusted = margin + line

    # Linha inteira ou meia
    if line % 0.5 == 0:
        if adjusted > 0:
            return 1.0
        if adjusted == 0:
            return 0.0
        return -1.0

    # Linha quarto (±0.25 ou ±0.75) — split
    floor_line = (line // 0.5) * 0.5
    ceil_line = floor_line + 0.5

    adj_floor = margin + floor_line
    adj_ceil = margin + ceil_line

    result_floor = 1.0 if adj_floor > 0 else (0.0 if adj_floor == 0 else -1.0)
    result_ceil = 1.0 if adj_ceil > 0 else (0.0 if adj_ceil == 0 else -1.0)

    return (result_floor + result_ceil) / 2.0


def _resolve_asian_handicap(home: int, away: int, side: str, line: float) -> bool | None:
    """Resolve AH como bool: ≥ 0 ganhou parcial/total, < 0 perdeu; 0.0 exato = push."""
    result = _asian_handicap_result(home, away, side, line)
    if result == 0.0:
        return None  # push — devolve stake
    return result > 0


def _resolve_over_under(total: int, line: float, outcome: str) -> bool | None:
    """Over/under: outcome 'yes'/'no' para total de gols."""
    over = total > line
    under = total < line
    if total == line:
        return None  # push (linhas inteiras)
    if outcome.lower() in ("yes", "sim"):
        return over
    return under


def resolve_bet(
    market: str,
    outcome: str,
    result: GameResult,
) -> bool | None:
    """Resolve uma aposta in-play dado o resultado final do jogo.

    Returns:
        True  → ganhou
        False → perdeu
        None  → não pode ser resolvido (dados insuficientes, push, ou mercado
                não suportado)
    """
    market = market.strip().lower()
    outcome = outcome.strip().lower()

    # ── 1X2 por período ──────────────────────────────────────────────────────
    if market in ("h2h", "ft_h2h"):
        return _resolve_h2h(result.ft_home, result.ft_away, outcome)

    if market == "1h_h2h":
        if result.ht_home is None:
            return None
        return _resolve_h2h(result.ht_home, result.ht_away, outcome)  # type: ignore[arg-type]

    if market == "2h_h2h":
        if result.sh_home is None:
            return None
        return _resolve_h2h(result.sh_home, result.sh_away, outcome)  # type: ignore[arg-type]

    # ── Handicap europeu e asiático ──────────────────────────────────────────
    parsed_hcap = parse_any_handicap_market(market)
    if parsed_hcap is not None:
        period, side, line, is_asian = parsed_hcap
        goals = _period_goals(result, period)
        if goals is None:
            return None
        home_g, away_g = goals
        if is_asian:
            return _resolve_asian_handicap(home_g, away_g, side, line)
        return _resolve_european_handicap(home_g, away_g, side, line)

    # ── Over/Under total de gols (FT) ─────────────────────────────────────────
    m = re.match(r"^over_(\d+)_(\d+)$", market)
    if m:
        line = float(f"{m.group(1)}.{m.group(2)}")
        total = result.ft_home + result.ft_away
        return _resolve_over_under(total, line, outcome)

    # ── Over/Under 1T ─────────────────────────────────────────────────────────
    m = re.match(r"^1h_over_(\d+)_(\d+)$", market)
    if m:
        if result.ht_home is None:
            return None
        line = float(f"{m.group(1)}.{m.group(2)}")
        total = result.ht_home + result.ht_away  # type: ignore[operator]
        return _resolve_over_under(total, line, outcome)

    # ── Over/Under 2T ─────────────────────────────────────────────────────────
    m = re.match(r"^2h_over_(\d+)_(\d+)$", market)
    if m:
        if result.sh_home is None:
            return None
        line = float(f"{m.group(1)}.{m.group(2)}")
        total = result.sh_home + result.sh_away  # type: ignore[operator]
        return _resolve_over_under(total, line, outcome)

    # ── Over/Under por equipe (FT) ────────────────────────────────────────────
    m = re.match(r"^(home|away)_over_(\d+)_(\d+)$", market)
    if m:
        side, int_part, dec_part = m.group(1), m.group(2), m.group(3)
        line = float(f"{int_part}.{dec_part}")
        team_goals = result.ft_home if side == "home" else result.ft_away
        return _resolve_over_under(team_goals, line, outcome)

    # ── BTTS ─────────────────────────────────────────────────────────────────
    if market == "btts":
        btts = result.ft_home > 0 and result.ft_away > 0
        return btts if outcome in ("yes", "sim") else not btts

    # ── BTTS + Over combos ────────────────────────────────────────────────────
    m = re.match(r"^combo_btts_over_(\d+)_(\d+)$", market)
    if m:
        line = float(f"{m.group(1)}.{m.group(2)}")
        total = result.ft_home + result.ft_away
        btts = result.ft_home > 0 and result.ft_away > 0
        won = btts and total > line
        return won if outcome in ("yes", "sim") else not won

    # ── Placar exato por período ──────────────────────────────────────────────
    # Formato: ft_cs_A_B, 1h_cs_A_B, 2h_cs_A_B
    m = re.match(r"^(ft|1h|2h)_cs_(\d+)_(\d+)$", market)
    if m:
        period = m.group(1)
        target_h, target_a = int(m.group(2)), int(m.group(3))
        goals = _period_goals(result, period)
        if goals is None:
            return None
        actual_won = goals[0] == target_h and goals[1] == target_a
        return actual_won if outcome in ("yes", "sim") else not actual_won

    # ── Total exato de gols por período (exact_N) ─────────────────────────────
    m = re.match(r"^(ft|1h|2h)_exact_(\d+(?:plus)?)$", market)
    if m:
        period = m.group(1)
        goals = _period_goals(result, period)
        if goals is None:
            return None
        total = goals[0] + goals[1]
        target_str = m.group(2)
        if target_str.endswith("plus"):
            target = int(target_str[:-4])
            actual_won = total >= target
        else:
            target = int(target_str)
            actual_won = total == target
        return actual_won if outcome in ("yes", "sim") else not actual_won

    return None


def build_ht_scores(ticks_df: "pd.DataFrame") -> "dict[int, tuple[int, int]]":  # type: ignore[name-defined]
    """Extrai placar do intervalo por evento a partir dos ticks ao vivo.

    Estratégia: preferir ticks com period_label=='HT'; fallback no último tick
    com period_label=='1H' (máximo minuto do 1T).

    Returns:
        Dict event_id → (ht_home, ht_away)
    """
    import pandas as pd

    df = ticks_df[["event_id", "minute", "home_score", "away_score", "period_label"]].copy()
    df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce")
    df = df.dropna(subset=["event_id"])
    df["event_id"] = df["event_id"].astype(int)

    ht_scores: dict[int, tuple[int, int]] = {}

    for event_id, group in df.groupby("event_id"):
        eid = int(event_id)

        # Preferência 1: ticks com period_label == 'HT'
        ht_ticks = group[group["period_label"] == "HT"]
        if not ht_ticks.empty:
            row = ht_ticks.iloc[0]
            h = int(row["home_score"]) if pd.notna(row.get("home_score")) else None
            a = int(row["away_score"]) if pd.notna(row.get("away_score")) else None
            if h is not None and a is not None:
                ht_scores[eid] = (h, a)
                continue

        # Preferência 2: último tick do 1T (maior minuto com period_label == '1H')
        fh_ticks = group[group["period_label"] == "1H"]
        if not fh_ticks.empty:
            fh_ticks = fh_ticks.dropna(subset=["minute"])
            fh_ticks["minute"] = pd.to_numeric(fh_ticks["minute"], errors="coerce")
            fh_ticks = fh_ticks.dropna(subset=["minute"])
            if not fh_ticks.empty:
                row = fh_ticks.loc[fh_ticks["minute"].idxmax()]
                h = int(row["home_score"]) if pd.notna(row.get("home_score")) else None
                a = int(row["away_score"]) if pd.notna(row.get("away_score")) else None
                if h is not None and a is not None:
                    ht_scores[eid] = (h, a)

    return ht_scores


__all__ = ["GameResult", "resolve_bet", "build_ht_scores"]
