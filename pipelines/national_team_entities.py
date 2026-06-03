"""Lexicon de seleções nacionais para extração em notícias (Sprint 4)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from schemas.national_teams import NATIONAL_ALIASES, normalize_national_team

SQUADS_PATH = Path(__file__).resolve().parent.parent / "data" / "wc" / "squads_2026.json"

EXTRA_PHRASES: dict[str, str] = {
    "seleção brasileira": "Brasil",
    "selecao brasileira": "Brasil",
    "seleção argentina": "Argentina",
    "seleção francesa": "França",
    "seleção inglesa": "Inglaterra",
    "seleção espanhola": "Espanha",
    "seleção portuguesa": "Portugal",
    "seleção alemã": "Alemanha",
    "selecao alema": "Alemanha",
    "seleção italiana": "Itália",
    "seleção holandesa": "Holanda",
    "seleção mexicana": "México",
    "seleção uruguaia": "Uruguai",
    "seleção japonesa": "Japão",
    "seleção marroquina": "Marrocos",
    "seleção americana": "Estados Unidos",
    "team usa": "Estados Unidos",
    "copa do mundo": "",
    "world cup": "",
}


def _squads_canonical_names() -> set[str]:
    if not SQUADS_PATH.exists():
        return set()
    data = json.loads(SQUADS_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for squad in data.get("squads", []):
        team = squad.get("team") or squad.get("country")
        if team:
            names.add(normalize_national_team(str(team)))
    return names


@lru_cache(maxsize=1)
def national_team_search_terms() -> list[tuple[str, str]]:
    """(termo no texto, nome canônico) ordenado do mais longo ao mais curto."""
    canonical: set[str] = set(_squads_canonical_names())
    canonical.update(NATIONAL_ALIASES.values())
    canonical.update(NATIONAL_ALIASES.keys())

    terms: dict[str, str] = {}
    for alias, name in NATIONAL_ALIASES.items():
        if alias and name:
            terms[alias.casefold()] = normalize_national_team(name)
    for phrase, name in EXTRA_PHRASES.items():
        if name:
            terms[phrase.casefold()] = normalize_national_team(name)
    for name in canonical:
        if name:
            terms[name.casefold()] = normalize_national_team(name)

    return sorted(
        ((term, canon) for term, canon in terms.items() if len(term) >= 3),
        key=lambda x: len(x[0]),
        reverse=True,
    )


def extract_national_teams(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    lower = text.casefold()
    found: list[str] = []
    seen: set[str] = set()

    for term, canon in national_team_search_terms():
        if term not in lower:
            continue
        if not _term_present(lower, term):
            continue
        key = canon.casefold()
        if key in seen:
            continue
        seen.add(key)
        found.append(canon)

    return found


def _term_present(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"(?<![\wáàâãéêíóôõúç]){re.escape(term)}(?![\wáàâãéêíóôõúç])", text) is not None
