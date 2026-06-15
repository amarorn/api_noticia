"""Testes da inbox CSV semi-automática (Fase A+)."""
from __future__ import annotations

import json

import pytest

from ingest.user_transactions.store import load_transactions
from ingest.user_transactions.wallet_inbox import (
    file_sha256,
    get_wallet_sync_status,
    import_csv_file,
    inbox_root,
    list_pending_csvs,
    scan_inbox,
)

SAMPLE_CSV = """Dados da carteira para teste

DataHoraDaTransação,Transação,Método de Pagamento,Valor,SaldoEmDinheiro,SaldoEmDinheiroAnterior,SaldoBônus,SaldoBônusAnterior,NomeDoJogo
2026-06-09 19:28:10.215,bilhete colocado,,15.00,370.17,385.17,0.00,0.00,me-INHS-INPLAY-SB_BR
2026-06-09 19:06:15.317,valor ganhado,,49.25,430.17,380.92,0.00,0.00,me-INHS-INPLAY-SB_BR
"""


@pytest.fixture
def lake(tmp_path, monkeypatch):
    from config import settings as s

    monkeypatch.setattr(s, "lake_root", tmp_path)
    monkeypatch.setattr(s, "wallet_inbox_enabled", True)
    monkeypatch.setattr(s, "wallet_inbox_dir", "inbox/wallet")
    return tmp_path


def _write_inbox_csv(lake, user_id: str, name: str = "extrato.csv"):
    folder = inbox_root(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(SAMPLE_CSV, encoding="utf-8")
    return path


class TestWalletInbox:
    def test_import_moves_to_processed(self, lake):
        path = _write_inbox_csv(lake, "teste")
        result = import_csv_file(path, "teste")
        assert result.imported is True
        assert result.n_rows == 2
        assert not path.exists()
        assert (inbox_root("teste") / "processed").exists()
        assert list_pending_csvs("teste") == []

    def test_idempotent_by_hash(self, lake):
        path = _write_inbox_csv(lake, "teste")
        first = import_csv_file(path, "teste")
        assert first.imported is True

        path2 = inbox_root("teste") / "extrato2.csv"
        path2.write_text(SAMPLE_CSV, encoding="utf-8")
        second = import_csv_file(path2, "teste")
        assert second.skipped is True
        assert second.reason == "ja_importado"

    def test_scan_inbox_imports_multiple(self, lake):
        _write_inbox_csv(lake, "u1", "a.csv")
        folder = inbox_root("u1")
        (folder / "b.csv").write_text(
            SAMPLE_CSV.replace("15.00", "20.00"),
            encoding="utf-8",
        )
        outcome = scan_inbox("u1", reconcile=False)
        assert outcome.n_imported == 2
        df = load_transactions("u1")
        assert len(df) == 4

    def test_registry_persisted(self, lake):
        path = _write_inbox_csv(lake, "teste")
        import_csv_file(path, "teste")
        reg_path = inbox_root() / "_registry.json"
        assert reg_path.exists()
        data = json.loads(reg_path.read_text(encoding="utf-8"))
        assert len(data["files"]) == 1

    def test_sync_status_pending_and_stale(self, lake, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "wallet_inbox_stale_days", 3)
        _write_inbox_csv(lake, "u2")
        status = get_wallet_sync_status("u2")
        assert status["n_pending"] == 1
        assert status["stale"] is False
        assert "inbox/wallet/u2" in status["inbox_dir"]

    def test_file_sha256_stable(self, lake):
        path = _write_inbox_csv(lake, "x")
        h1 = file_sha256(path)
        h2 = file_sha256(path)
        assert h1 == h2

    def test_invalid_csv_skipped(self, lake):
        folder = inbox_root("bad")
        folder.mkdir(parents=True)
        bad = folder / "vazio.csv"
        bad.write_text("col1,col2\n", encoding="utf-8")
        result = import_csv_file(bad, "bad")
        assert result.skipped is True
        assert result.reason == "csv_vazio_ou_invalido"
