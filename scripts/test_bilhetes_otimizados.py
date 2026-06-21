#!/usr/bin/env python3
"""Script de teste rápido para bilhetes otimizados."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_bilhetes(event_id: int = 11511115):
    from ingest.superbet.advice import run_live_advice
    from models.wc_artifact import load_or_train_wc_predictor

    predictor, _ = load_or_train_wc_predictor(force=False, allow_train=False)

    payload = await asyncio.to_thread(
        run_live_advice,
        event_id,
        predictor,
        phase="friendly",
        bankroll=1000,
        save_bronze=False,
        save_tick=False,
        use_sofascore_live=False,
        fast=True,
    )

    opt = payload.get("optimized_tickets", {})
    total = sum(len(opt.get(p, [])) for p in ["1h", "2h", "ft", "mixed"])

    print(f"Evento: {payload['home_team']} x {payload['away_team']} ({payload['minute']}', {payload.get('current_score', '0x0')})")
    print(f"Total bilhetes: {total}")

    for period in ["ft", "mixed", "1h", "2h"]:
        tickets = opt.get(period, [])
        if tickets:
            print(f"\n{period.upper()}: {len(tickets)} bilhete(s)")
            for t in tickets[:1]:
                print(f"  {t['n_legs']} pernas · Odd {t['combined_odd']:.2f} · EV +{t['combined_ev']*100:.1f}%")
                for leg in t["legs"]:
                    print(f"    - {leg['label']}")

    return total > 0


if __name__ == "__main__":
    event_id = int(sys.argv[1]) if len(sys.argv) > 1 else 11511115
    ok = asyncio.run(test_bilhetes(event_id))
    sys.exit(0 if ok else 1)
