#!/usr/bin/env python3
"""Importa baselines KXL do TXT para data/wc/team_baselines.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "wc" / "team_baselines.json"


def parse_kxl_txt(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r":\s*0+(\d+)", r": \1", raw)
    chunks: list[dict] = []
    for part in re.split(r"\]\s*\[", raw.strip()):
        part = part.strip()
        if not part.startswith("["):
            part = "[" + part
        if not part.endswith("]"):
            part = part + "]"
        chunks.extend(json.loads(part))
    seen: dict[str, dict] = {}
    for entry in chunks:
        name = entry.get("selecao", "")
        if name and name not in seen:
            seen[name] = entry
    return list(seen.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Arquivo TXT com arrays JSON KXL")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.source.is_file():
        print(f"Arquivo não encontrado: {args.source}", file=sys.stderr)
        return 1
    teams = parse_kxl_txt(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "source": "kxl_copa_2026", "teams": teams}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Importadas {len(teams)} seleções -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
