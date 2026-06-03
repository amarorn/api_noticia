#!/usr/bin/env python3
"""Extrai convocações da Copa 2026 a partir do markdown exportado do ge.globo.com."""

from __future__ import annotations

import json
import re
from pathlib import Path

SOURCE_URL = (
    "https://ge.globo.com/rj/copa-do-mundo/noticia/2026/05/15/"
    "veja-todas-as-convocacoes-para-a-copa-do-mundo-2026.ghtml"
)
UPDATED_AT = "2026-06-02"

ROLE_TO_POSITION = {
    "goleiros": "GK",
    "defensores": "DEF",
    "meio-campistas": "MID",
    "meias": "MID",
    "atacantes": "ATK",
    "meias/atacantes": "MID_FWD",
    "meias/atacante": "MID_FWD",
    "meia/atacantes": "MID_FWD",
}

TEAM_ALIASES = {
    "Curaçao": "Curaçau",
    "RD Congo": "República Democrática do Congo",
    "Coreia do Sul ": "Coreia do Sul",
    "Gana ": "Gana",
    "**Catar**": "Catar",
    "**Estados Unidos**": "Estados Unidos",
}

SKIP_HEADERS = {
    "Cada seleção levará 26 jogadores convocados para o Mundial da América do Norte",
    "Veja as convocações:",
    "Veja camisas extravagantes dos goleiros em Copas dos anos 90 que marcaram os mundiais",
    "O novo astro da França que vai à primeira Copa em seu auge e sem saber citar destaque do Brasil",
    "Ainda está no topo? Argentina defende título da Copa do Mundo sem enfrentar europeus no ciclo",
    "Copa do Mundo 2026: Brasil está entre as poucas seleções sem jogadores nascidos em outros países",
    "CT da seleção brasileira na Copa é novo e teve investimento acima de R$ 500 milhões; veja",
    "Jogou a toalha? Diretor da Inglaterra é pessimista sobre título na Copa do Mundo",
    "Técnico de Gana brigou com CR7, treinou galácticos do Real Madrid e será recordista na Copa do Mundo",
    "Limite de ingressos para familiares gera novo atrito na França às vésperas da Copa do Mundo",
    'Adversário do Brasil na Copa, Haiti goleia Nova Zelândia em amistoso',
    '"Estou com medo": brasileiros reagem à goleada do Haiti em amistoso',
}


def normalize_team(name: str) -> str:
    cleaned = name.strip().strip("*").strip()
    return TEAM_ALIASES.get(cleaned, TEAM_ALIASES.get(name, cleaned))


def normalize_role(raw: str) -> tuple[str, str]:
    key = raw.strip().lower().replace(" ", "")
    key = key.replace("meio-campistas", "meio-campistas")
    lowered = raw.strip().lower()
    for pattern, pos in ROLE_TO_POSITION.items():
        if pattern.replace("/", "") in lowered.replace("-", "").replace(" ", "") or pattern in lowered:
            return raw.strip(), pos
    if "goleiro" in lowered:
        return raw.strip(), "GK"
    if "defensor" in lowered:
        return raw.strip(), "DEF"
    if "atacante" in lowered and "meia" not in lowered:
        return raw.strip(), "ATK"
    if "meia" in lowered or "meio" in lowered:
        return raw.strip(), "MID_FWD"
    return raw.strip(), "MID_FWD"


def split_players(blob: str) -> list[str]:
    blob = blob.strip().rstrip(";").rstrip(".")
    blob = blob.replace(";", ",")
    parts = re.split(r",\s*|\s+e\s+", blob)
    cleaned: list[str] = []
    for part in parts:
        part = part.strip().lstrip("·").strip()
        if part:
            cleaned.append(part)
    return cleaned


def parse_player(entry: str) -> dict[str, str | None]:
    entry = entry.strip().rstrip(".")
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", entry)
    if match:
        return {"name": match.group(1).strip(), "club": match.group(2).strip()}
    return {"name": entry, "club": None}


def parse_markdown(text: str) -> list[dict]:
    squads: list[dict] = []
    current_team: str | None = None
    current_sections: list[dict] = []

    def flush() -> None:
        nonlocal current_team, current_sections
        if current_team and current_sections:
            squads.append(_build_squad(current_team, current_sections))
        current_team = None
        current_sections = []

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("## "):
            flush()
            header = stripped[3:].strip()
            if header in SKIP_HEADERS or header.startswith("Veja "):
                continue
            current_team = normalize_team(header)
            current_sections = []
            continue

        bold_team = re.match(r"^\*\*(.+?)\*\*\s*$", stripped)
        if bold_team:
            candidate = normalize_team(bold_team.group(1))
            if candidate not in SKIP_HEADERS and len(candidate) > 2:
                flush()
                current_team = candidate
                current_sections = []
            continue

        if not current_team:
            continue

        role_match = re.match(r"^\*\s*\*\*(.+?)\*\*\s*:?\s*(.+)$", stripped)
        if not role_match:
            continue

        role_label, players_blob = role_match.groups()
        role_label, position = normalize_role(role_label)
        players = [parse_player(p) for p in split_players(players_blob)]
        if players:
            current_sections.append(
                {
                    "role": role_label,
                    "position": position,
                    "players": players,
                }
            )

    flush()
    squads.sort(key=lambda s: s["team"].casefold())
    return squads


def _build_squad(team: str, sections: list[dict]) -> dict:
    total = sum(len(s["players"]) for s in sections)
    return {
        "team": team,
        "player_count": total,
        "sections": sections,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    md_candidates = [
        root / "data" / "wc" / "ge_convocacoes_2026.md",
        Path.home()
        / ".cursor/projects/Users-amaro-Documents-Cactus-api-noticia/uploads"
        / "veja-todas-as-convocacoes-para-a-copa-do-mundo-2026.ghtml-0.md",
    ]
    md_path = next((p for p in md_candidates if p.exists()), md_candidates[0])
    if not md_path.exists():
        raise SystemExit(f"Markdown não encontrado: {md_path}")

    text = md_path.read_text(encoding="utf-8")
    squads = parse_markdown(text)

    out_path = root / "data" / "wc" / "squads_2026.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": 2026,
        "competition": "Copa do Mundo FIFA 2026",
        "source_url": SOURCE_URL,
        "updated_at": UPDATED_AT,
        "team_count": len(squads),
        "squads": squads,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(squads)} squads to {out_path}")
    for s in squads:
        print(f"  {s['team']}: {s['player_count']} jogadores")


if __name__ == "__main__":
    main()
