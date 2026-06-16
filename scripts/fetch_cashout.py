#!/usr/bin/env python3
"""Captura valores de cash-out da Superbet para apostas cadastradas localmente.

Uso:
    python scripts/fetch_cashout.py [--all]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingest.superbet.cashout_client import fetch_cashout_value


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura cash-out Superbet")
    parser.add_argument("--all", action="store_true", help="Atualiza todas as apostas, não só as sem cash-out")
    args = parser.parse_args()

    bets_file = Path("data/lake/user_open_bets.json")
    if not bets_file.exists():
        print("Nenhuma aposta cadastrada.")
        return

    store = json.loads(bets_file.read_text(encoding="utf-8"))
    bets = store.get("bets", [])
    updated = 0

    for b in bets:
        if b.get("status") != "open":
            continue
        ticket = b.get("ticket_code")
        if not ticket:
            continue
        if not args.all and b.get("cashout_value") is not None:
            continue
        result = fetch_cashout_value(ticket)
        if result and result.get("eligible"):
            cashout = float(result.get("value", 0))
            b["cashout_value"] = round(cashout, 2)
            print(f"✅ {b.get('event_name', ticket)} — cash-out R$ {b['cashout_value']}")
            updated += 1
        elif result:
            b["cashout_value"] = 0.0
            reason = result.get("unavailabilityReason", "unknown")
            print(f"⛔ {b.get('event_name', ticket)} — ineligível ({reason})")
            updated += 1
        else:
            print(f"❌ {b.get('event_name', ticket)} — erro na consulta")

    if updated:
        bets_file.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{updated} apostas atualizadas.")
    else:
        print("Nenhuma atualização.")


if __name__ == "__main__":
    main()
