"""Testes da Fase 4 — Feedback Loop (CSV upload + reconciliação + retreino)."""
from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd

from ingest.user_transactions.parser import parse_user_csv
from ingest.user_transactions.store import (
    load_transactions,
    save_transactions_bronze,
)
from pipelines.user_bet_analytics import (
    compute_model_errors_heatmap,
    compute_wallet_summary,
)
from pipelines.user_bet_reconciliation import (
    SnapshotRef,
    find_snapshot_for_bet,
    pair_placed_with_outcome,
)
from schemas.user_transaction import UserTransactionRow

SAMPLE_CSV = """Dados da carteira para teste

DataHoraDaTransação,Transação,Método de Pagamento,Valor,SaldoEmDinheiro,SaldoEmDinheiroAnterior,SaldoBônus,SaldoBônusAnterior,NomeDoJogo
2026-06-09 19:28:12.694,bilhete confirmado,,0.00,370.17,370.17,0.00,0.00,me-INHS-INPLAY-SB_BR
2026-06-09 19:28:10.215,bilhete colocado,,15.00,370.17,385.17,0.00,0.00,me-INHS-INPLAY-SB_BR
2026-06-09 18:32:23.304,bilhete colocado,,25.00,380.92,405.92,0.00,0.00,me-INHS-INPLAY-SB_BR
2026-06-09 19:06:15.317,valor ganhado,,49.25,430.17,380.92,0.00,0.00,me-INHS-INPLAY-SB_BR
2026-06-09 14:54:26.941,depósito,pix,300.00,449.33,149.33,0.00,0.00,UNKNOWN
"""


class TestParser:
    def test_parse_basic_csv(self):
        rows = parse_user_csv(SAMPLE_CSV, "teste", str(uuid.uuid4()))
        assert len(rows) == 5
        assert all(isinstance(r, UserTransactionRow) for r in rows)
        assert any(r.is_inplay_bet for r in rows)

    def test_parse_recognizes_bet_types(self):
        rows = parse_user_csv(SAMPLE_CSV, "teste", str(uuid.uuid4()))
        types = {r.transaction_type for r in rows}
        assert "bilhete colocado" in types
        assert "bilhete confirmado" in types
        assert "valor ganhado" in types
        assert "depósito" in types

    def test_parse_amount_decimals(self):
        rows = parse_user_csv(SAMPLE_CSV, "teste", str(uuid.uuid4()))
        wins = [r for r in rows if r.is_win]
        assert len(wins) == 1
        assert abs(wins[0].amount - 49.25) < 1e-3

    def test_parse_inplay_flag(self):
        rows = parse_user_csv(SAMPLE_CSV, "teste", str(uuid.uuid4()))
        inplay_rows = [r for r in rows if r.is_inplay_bet]
        non_inplay = [r for r in rows if not r.is_inplay_bet]
        assert len(inplay_rows) == 4  # 4 INPLAY-SB_BR
        assert len(non_inplay) == 1  # 1 depósito UNKNOWN

    def test_parse_empty_returns_empty(self):
        rows = parse_user_csv("", "teste", str(uuid.uuid4()))
        assert rows == []


class TestStorage:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "lake_root", tmp_path)
        rows = parse_user_csv(SAMPLE_CSV, "teste", "uid1")
        save_transactions_bronze(rows, "teste", "uid1")

        df = load_transactions("teste")
        assert len(df) == 5
        assert "transaction_at" in df.columns
        assert df["user_id"].iloc[0] == "teste"


class TestPairPlacedWithOutcome:
    def test_pair_basic(self):
        df = pd.DataFrame([
            {
                "transaction_at": datetime(2026, 6, 9, 18, 32, 23),
                "transaction_type": "bilhete colocado",
                "amount": 25.0,
                "game_name": "me-INHS-INPLAY-SB_BR",
                "user_id": "u",
                "upload_id": "uid",
            },
            {
                "transaction_at": datetime(2026, 6, 9, 19, 6, 15),
                "transaction_type": "valor ganhado",
                "amount": 49.25,
                "game_name": "me-INHS-INPLAY-SB_BR",
                "user_id": "u",
                "upload_id": "uid",
            },
        ])
        pairs = pair_placed_with_outcome(df)
        assert len(pairs) == 1
        assert pairs[0]["stake"] == 25.0
        assert pairs[0]["won_amount"] == 49.25
        assert pairs[0]["won"] is True

    def test_pair_skips_cancelled(self):
        df = pd.DataFrame([
            {
                "transaction_at": datetime(2026, 6, 9, 18, 32, 23),
                "transaction_type": "bilhete colocado",
                "amount": 25.0,
                "game_name": "me-INHS-INPLAY-SB_BR",
                "user_id": "u",
                "upload_id": "uid",
            },
            {
                "transaction_at": datetime(2026, 6, 9, 18, 32, 25),
                "transaction_type": "bilhete cancelado",
                "amount": 25.0,
                "game_name": "me-INHS-INPLAY-SB_BR",
                "user_id": "u",
                "upload_id": "uid",
            },
        ])
        pairs = pair_placed_with_outcome(df)
        assert len(pairs) == 0

    def test_pair_only_inplay(self):
        df = pd.DataFrame([
            {
                "transaction_at": datetime(2026, 6, 9, 12, 0, 0),
                "transaction_type": "bilhete colocado",
                "amount": 5.0,
                "game_name": "Slot Game",  # casino, não inplay
                "user_id": "u",
                "upload_id": "uid",
            },
        ])
        pairs = pair_placed_with_outcome(df)
        assert len(pairs) == 0


class TestFindSnapshotForBet:
    def test_match_within_window(self):
        snap = SnapshotRef(
            event_id=123,
            path=__import__("pathlib").Path("/tmp/x.json"),
            timestamp=datetime(2026, 6, 9, 22, 30, 0),  # UTC
            home_team="Brasil",
            away_team="Argentina",
            is_live=True,
            minute=60,
            home_score=1,
            away_score=0,
        )
        # Bet em horário local BR (UTC-3) → 19:30 local = 22:30 UTC
        bet_at = datetime(2026, 6, 9, 19, 30, 0)
        result = find_snapshot_for_bet(bet_at, [snap])
        assert result.matched
        assert result.snapshot is snap
        assert result.confidence > 0.9

    def test_no_match_outside_window(self):
        snap = SnapshotRef(
            event_id=123,
            path=__import__("pathlib").Path("/tmp/x.json"),
            timestamp=datetime(2026, 6, 9, 22, 30, 0),
            home_team="Brasil",
            away_team="Argentina",
            is_live=True,
        )
        bet_at = datetime(2026, 6, 9, 19, 0, 0)  # 30 min antes (UTC: 22:00 vs 22:30)
        result = find_snapshot_for_bet(bet_at, [snap], window_seconds=180)
        assert not result.matched

    def test_skip_non_live_snapshots(self):
        snap = SnapshotRef(
            event_id=123,
            path=__import__("pathlib").Path("/tmp/x.json"),
            timestamp=datetime(2026, 6, 9, 22, 30, 0),
            home_team="Brasil",
            away_team="Argentina",
            is_live=False,  # pré-jogo
        )
        bet_at = datetime(2026, 6, 9, 19, 30, 0)
        result = find_snapshot_for_bet(bet_at, [snap])
        assert not result.matched


class TestAnalytics:
    def test_summary_empty_user(self):
        summary = compute_wallet_summary("usuario_inexistente_xyz")
        assert summary["n_transactions"] == 0
        assert summary["pnl"] == 0.0

    def test_summary_with_data(self, tmp_path, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "lake_root", tmp_path)
        rows = parse_user_csv(SAMPLE_CSV, "teste_analytics", "uid_an")
        save_transactions_bronze(rows, "teste_analytics", "uid_an")

        summary = compute_wallet_summary("teste_analytics")
        assert summary["n_transactions"] == 5
        assert summary["n_bets_placed"] == 2
        assert summary["total_deposits"] == 300.0
        # P&L = won (49.25) - net_staked (15+25 = 40 - 0 cancelados) = 9.25
        assert abs(summary["pnl"] - 9.25) < 1e-2

    def test_model_errors_empty(self):
        result = compute_model_errors_heatmap("usuario_xyz_inexistente")
        assert result["buckets"] == []
