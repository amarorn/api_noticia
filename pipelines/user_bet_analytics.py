"""Analytics da carteira do usuário: KPIs, P&L diário, breakdowns.

Lê transações do bronze + reconciliação do silver e gera estruturas para o
frontend (`/carteira`).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from config import settings
from ingest.user_transactions.store import load_transactions
from pipelines.user_bet_reconciliation import load_reconciliation

_BR_TZ = ZoneInfo("America/Sao_Paulo")


def _today_br() -> date:
    return datetime.now(_BR_TZ).date()


def _max_period_end(last_tx: pd.Timestamp) -> pd.Timestamp:
    """Estende period_end até hoje (BR) quando o CSV não inclui o dia atual."""
    today_end = pd.Timestamp(_today_br()).replace(hour=23, minute=59, second=59)
    if last_tx.tzinfo is not None:
        today_end = today_end.tz_localize(last_tx.tzinfo)
    return max(last_tx, today_end)


def _parse_bet_date(iso_ts: str) -> date | None:
    """Converte timestamp ISO da aposta para data em horário de Brasília."""
    if not iso_ts:
        return None
    try:
        ts = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            return dt.date()
        return dt.astimezone(_BR_TZ).date()
    except ValueError:
        return None


def _empty_daily_row(d: date) -> dict[str, Any]:
    return {
        "date": str(d),
        "staked": 0.0,
        "won": 0.0,
        "pnl": 0.0,
        "n_bets": 0,
        "is_today": d == _today_br(),
    }


def _fill_daily_gaps(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preenche dias sem transação entre o primeiro registro e hoje (BR)."""
    if not daily:
        return daily
    by_date = {d["date"]: d for d in daily}
    dates = sorted(date.fromisoformat(d["date"]) for d in daily)
    end = max(dates[-1], _today_br())
    out: list[dict[str, Any]] = []
    cur = dates[0]
    while cur <= end:
        key = str(cur)
        if key in by_date:
            row = dict(by_date[key])
        else:
            row = _empty_daily_row(cur)
        row["is_today"] = cur == _today_br()
        out.append(row)
        cur += timedelta(days=1)
    return out


def _load_supplemental_bets(user_id: str) -> tuple[list[dict], list[dict]]:
    """Lê apostas abertas/liquidadas (extensão/API) não presentes no CSV."""
    root = Path(settings.lake_root)
    open_bets: list[dict] = []
    settled: list[dict] = []

    open_path = root / "user_open_bets.json"
    if open_path.exists():
        data = json.loads(open_path.read_text(encoding="utf-8"))
        for b in data.get("bets", []):
            if b.get("status") != "open":
                continue
            uid = b.get("user_id")
            if uid and uid != user_id:
                continue
            open_bets.append(b)

    settled_path = root / "user_settled_bets.json"
    if settled_path.exists():
        data = json.loads(settled_path.read_text(encoding="utf-8"))
        settled = list(data.get("bets", []))

    return open_bets, settled


def _merge_supplemental_daily(
    daily: list[dict[str, Any]],
    user_id: str,
) -> list[dict[str, Any]]:
    """Incorpora apostas da extensão/API nos dias ainda sem CSV (ex.: hoje)."""
    open_bets, settled = _load_supplemental_bets(user_id)
    if not open_bets and not settled:
        return daily

    by_date = {d["date"]: d for d in daily}

    for bet in open_bets:
        dkey = _parse_bet_date(bet.get("captured_at", ""))
        if dkey is None:
            continue
        key = str(dkey)
        row = by_date.setdefault(key, _empty_daily_row(dkey))
        stake = float(bet.get("stake", 0))
        row["staked"] = round(float(row["staked"]) + stake, 2)
        row["n_bets"] = int(row["n_bets"]) + 1
        row["pnl"] = round(float(row["pnl"]) - stake, 2)
        row["supplemental"] = True

    for bet in settled:
        dkey = _parse_bet_date(bet.get("placed_at") or bet.get("settled_at", ""))
        if dkey is None:
            continue
        key = str(dkey)
        row = by_date.setdefault(key, _empty_daily_row(dkey))
        stake = float(bet.get("stake", 0))
        profit = float(bet.get("profit", 0))
        row["staked"] = round(float(row["staked"]) + stake, 2)
        row["n_bets"] = int(row["n_bets"]) + 1
        row["won"] = round(float(row["won"]) + max(profit + stake, 0), 2)
        row["pnl"] = round(float(row["pnl"]) + profit, 2)
        row["supplemental"] = True

    out = sorted(by_date.values(), key=lambda x: x["date"])
    for row in out:
        row["is_today"] = row["date"] == str(_today_br())
    return out


def compute_wallet_summary(user_id: str) -> dict[str, Any]:
    """KPIs agregados do usuário."""
    df = load_transactions(user_id)
    if df.empty:
        return {
            "user_id": user_id,
            "n_transactions": 0,
            "n_bets_placed": 0,
            "n_bets_won": 0,
            "hit_rate": 0.0,
            "total_staked": 0.0,
            "total_won": 0.0,
            "pnl": 0.0,
            "roi": 0.0,
            "total_deposits": 0.0,
            "current_balance": 0.0,
            "period_start": None,
            "period_end": None,
            "daily_pnl": [],
            "by_game_type": [],
            "balance_series": [],
        }

    df = df.sort_values("transaction_at").reset_index(drop=True)

    n_placed = int((df["transaction_type"] == "bilhete colocado").sum())
    n_cancelled = int((df["transaction_type"] == "bilhete cancelado").sum())
    n_won = int(((df["transaction_type"] == "valor ganhado") & (df["amount"] > 0)).sum())
    total_staked = float(df.loc[df["transaction_type"] == "bilhete colocado", "amount"].sum())
    total_cancelled = float(df.loc[df["transaction_type"] == "bilhete cancelado", "amount"].sum())
    total_won = float(df.loc[df["transaction_type"] == "valor ganhado", "amount"].sum())
    total_deposits = float(df.loc[df["transaction_type"] == "depósito", "amount"].sum())

    # Net staked: subtrai cancelados (que devolveram o valor)
    net_staked = total_staked - total_cancelled
    pnl = total_won - net_staked
    roi = pnl / net_staked if net_staked > 0 else 0.0

    # Hit rate: bilhetes confirmados (não cancelados) que ganharam
    n_confirmed = n_placed - n_cancelled
    hit_rate = n_won / n_confirmed if n_confirmed > 0 else 0.0

    # Saldo atual: último valor de SaldoEmDinheiro
    current_balance = float(df.iloc[-1]["cash_balance"]) if not df.empty else 0.0

    # P&L diário
    df_day = df.copy()
    df_day["date"] = df_day["transaction_at"].dt.date
    daily = []
    for day_key, grp in df_day.groupby("date"):
        d_staked = float(grp.loc[grp["transaction_type"] == "bilhete colocado", "amount"].sum())
        d_cancelled = float(grp.loc[grp["transaction_type"] == "bilhete cancelado", "amount"].sum())
        d_won = float(grp.loc[grp["transaction_type"] == "valor ganhado", "amount"].sum())
        d_pnl = d_won - (d_staked - d_cancelled)
        daily.append({
            "date": str(day_key),
            "staked": round(d_staked - d_cancelled, 2),
            "won": round(d_won, 2),
            "pnl": round(d_pnl, 2),
            "n_bets": int((grp["transaction_type"] == "bilhete colocado").sum()),
            "is_today": day_key == _today_br(),
        })

    daily.sort(key=lambda x: x["date"])
    daily = _fill_daily_gaps(daily)
    daily = _merge_supplemental_daily(daily, user_id)

    # Breakdown por tipo de jogo (in-play vs casino vs UNKNOWN)
    by_game = []
    df_bets = df[df["transaction_type"].isin(["bilhete colocado", "valor ganhado"])]
    if not df_bets.empty:
        df_bets = df_bets.copy()
        df_bets["category"] = df_bets["game_name"].apply(_categorize_game)
        for cat, grp in df_bets.groupby("category"):
            cat_staked = float(grp.loc[grp["transaction_type"] == "bilhete colocado", "amount"].sum())
            cat_won = float(grp.loc[grp["transaction_type"] == "valor ganhado", "amount"].sum())
            cat_pnl = cat_won - cat_staked
            n_bets_cat = int((grp["transaction_type"] == "bilhete colocado").sum())
            by_game.append({
                "category": cat,
                "staked": round(cat_staked, 2),
                "won": round(cat_won, 2),
                "pnl": round(cat_pnl, 2),
                "n_bets": n_bets_cat,
            })
        by_game.sort(key=lambda x: -abs(x["pnl"]))

    # Série de saldo ao longo do tempo (para gráfico de linha)
    balance_series = [
        {
            "at": row["transaction_at"].isoformat(),
            "balance": float(row["cash_balance"]),
            "type": row["transaction_type"],
        }
        for _, row in df.iterrows()
    ]

    return {
        "user_id": user_id,
        "n_transactions": len(df),
        "n_bets_placed": n_placed,
        "n_bets_won": n_won,
        "hit_rate": round(hit_rate, 4),
        "total_staked": round(net_staked, 2),
        "total_won": round(total_won, 2),
        "pnl": round(pnl, 2),
        "roi": round(roi, 4),
        "total_deposits": round(total_deposits, 2),
        "current_balance": round(current_balance, 2),
        "period_start": df["transaction_at"].min().isoformat(),
        "period_end": _max_period_end(df["transaction_at"].max()).isoformat(),
        "today": str(_today_br()),
        "daily_pnl": daily,
        "by_game_type": by_game,
        "balance_series": balance_series,
    }


def _categorize_game(game_name: str) -> str:
    """Classifica em: 'inplay', 'casino', 'outros'."""
    if not game_name:
        return "outros"
    upper = game_name.upper()
    if "INPLAY" in upper or "INHS" in upper:
        return "inplay"
    if "UNKNOWN" in upper:
        return "outros"
    return "casino"


def compute_reconciliation_table(
    user_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Tabela paginada de reconciliação."""
    df = load_reconciliation(user_id)
    if df.empty:
        return {"total": 0, "items": []}

    total = len(df)
    df_sorted = df.sort_values("placed_at", ascending=False)
    page = df_sorted.iloc[offset : offset + limit]

    items = []
    for _, row in page.iterrows():
        items.append({
            "placed_at": row["placed_at"].isoformat() if pd.notna(row.get("placed_at")) else None,
            "stake": float(row.get("stake", 0)),
            "won_amount": float(row.get("won_amount", 0)),
            "pnl": float(row.get("pnl", 0)),
            "won": bool(row.get("won", False)),
            "event_id": int(row["event_id"]) if pd.notna(row.get("event_id")) else None,
            "home_team": row.get("home_team"),
            "away_team": row.get("away_team"),
            "match_minute": int(row["match_minute"]) if pd.notna(row.get("match_minute")) else None,
            "home_score": int(row["home_score"]) if pd.notna(row.get("home_score")) else None,
            "away_score": int(row["away_score"]) if pd.notna(row.get("away_score")) else None,
            "match_confidence": float(row.get("match_confidence", 0)),
            "model_generosity_home": (
                float(row["model_generosity_home"])
                if pd.notna(row.get("model_generosity_home")) else None
            ),
            "model_generosity_away": (
                float(row["model_generosity_away"])
                if pd.notna(row.get("model_generosity_away")) else None
            ),
        })

    return {"total": total, "items": items}


def compute_model_errors_heatmap(user_id: str) -> dict[str, Any]:
    """Computa Brier por bucket de minuto e |goal_diff| para o heatmap.

    Brier por bilhete = (model_prob - won)² onde model_prob é uma proxy
    derivada da generosity_probs ou dos snapshots reconciliados.
    """
    df = load_reconciliation(user_id)
    if df.empty:
        return {"buckets": [], "min_buckets": [], "diff_buckets": []}

    df_valid = df[
        (df["match_confidence"].fillna(0) >= 0.5)
        & df["event_id"].notna()
    ].copy()

    if df_valid.empty:
        return {"buckets": [], "min_buckets": [], "diff_buckets": []}

    # Buckets de minuto (0-15, 15-30, 30-45, 45-60, 60-75, 75-90+)
    df_valid["min_bucket"] = pd.cut(
        df_valid["match_minute"].fillna(0),
        bins=[0, 15, 30, 45, 60, 75, 200],
        labels=["0-15", "15-30", "30-45", "45-60", "60-75", "75+"],
        include_lowest=True,
    )
    df_valid["goal_diff"] = (
        df_valid["home_score"].fillna(0) - df_valid["away_score"].fillna(0)
    ).abs()
    df_valid["diff_bucket"] = pd.cut(
        df_valid["goal_diff"],
        bins=[-0.5, 0.5, 1.5, 2.5, 10],
        labels=["empate", "1-gol", "2-gols", "3+"],
        include_lowest=True,
    )

    # Brier proxy: usar 0.5 como prob neutra quando não há prob explícita
    df_valid["model_prob_proxy"] = df_valid.apply(_extract_prob_proxy, axis=1)
    df_valid["brier"] = (
        df_valid["model_prob_proxy"] - df_valid["won"].astype(float)
    ) ** 2

    # Heatmap: minuto × diff
    buckets = []
    for (min_b, diff_b), grp in df_valid.groupby(["min_bucket", "diff_bucket"], observed=True):
        if grp.empty:
            continue
        buckets.append({
            "min_bucket": str(min_b),
            "diff_bucket": str(diff_b),
            "n_bets": len(grp),
            "avg_brier": round(float(grp["brier"].mean()), 4),
            "hit_rate": round(float(grp["won"].mean()), 4),
            "total_pnl": round(float(grp["pnl"].sum()), 2),
        })

    # Marginais
    min_buckets = []
    for b, grp in df_valid.groupby("min_bucket", observed=True):
        min_buckets.append({
            "bucket": str(b),
            "n_bets": len(grp),
            "avg_brier": round(float(grp["brier"].mean()), 4),
            "hit_rate": round(float(grp["won"].mean()), 4),
            "total_pnl": round(float(grp["pnl"].sum()), 2),
        })

    diff_buckets = []
    for b, grp in df_valid.groupby("diff_bucket", observed=True):
        diff_buckets.append({
            "bucket": str(b),
            "n_bets": len(grp),
            "avg_brier": round(float(grp["brier"].mean()), 4),
            "hit_rate": round(float(grp["won"].mean()), 4),
            "total_pnl": round(float(grp["pnl"].sum()), 2),
        })

    return {
        "buckets": buckets,
        "min_buckets": min_buckets,
        "diff_buckets": diff_buckets,
        "n_total_bets": len(df_valid),
    }


def _extract_prob_proxy(row: pd.Series) -> float:
    """Extrai probabilidade do modelo do snapshot.

    Usa generosity como proxy quando 1X2 não está populado: generosity_home alta
    → modelo confiando no home → prob_home alta.

    Se não há dados, retorna 0.5 (neutro).
    """
    hs = row.get("home_score")
    as_ = row.get("away_score")
    p_home = row.get("prob_final_home")
    p_away = row.get("prob_final_away")
    p_draw = row.get("prob_final_draw")
    if p_home is not None and pd.notna(p_home) and hs is not None and as_ is not None:
        if hs > as_:
            return float(p_home)
        if hs < as_ and p_away is not None and pd.notna(p_away):
            return float(p_away)
        if p_draw is not None and pd.notna(p_draw):
            return float(p_draw)
        return float(p_home)

    gen_home = row.get("model_generosity_home")
    if gen_home is not None and pd.notna(gen_home):
        return float(gen_home)
    return 0.5
