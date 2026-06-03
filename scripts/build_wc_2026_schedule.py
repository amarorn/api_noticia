#!/usr/bin/env python3
"""Gera data/rounds/wc_2026.json a partir do calendário oficial FIFA (fase de grupos)."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/rounds/wc_2026.json"

# Grupos oficiais — sorteio FIFA (5 dez 2025), repescagens resolvidas (Tcheca, Bósnia, Turquia).
GROUPS: list[tuple[str, list[str]]] = [
    ("A", ["México", "África do Sul", "Coreia do Sul", "República Tcheca"]),
    ("B", ["Canadá", "Bósnia", "Catar", "Suíça"]),
    ("C", ["Brasil", "Marrocos", "Haiti", "Escócia"]),
    ("D", ["Estados Unidos", "Paraguai", "Austrália", "Turquia"]),
    ("E", ["Alemanha", "Curaçau", "Costa do Marfim", "Equador"]),
    ("F", ["Holanda", "Japão", "Suécia", "Tunísia"]),
    ("G", ["Bélgica", "Egito", "Irã", "Nova Zelândia"]),
    ("H", ["Espanha", "Cabo Verde", "Arábia Saudita", "Uruguai"]),
    ("I", ["França", "Senegal", "Iraque", "Noruega"]),
    ("J", ["Argentina", "Argélia", "Áustria", "Jordânia"]),
    ("K", ["Portugal", "República Democrática do Congo", "Uzbequistão", "Colômbia"]),
    ("L", ["Inglaterra", "Croácia", "Gana", "Panamá"]),
]

TEAM_EN: dict[str, str] = {
    "Mexico": "México",
    "South Africa": "África do Sul",
    "South Korea": "Coreia do Sul",
    "Korea Republic": "Coreia do Sul",
    "Czechia": "República Tcheca",
    "Canada": "Canadá",
    "Bosnia and Herzegovina": "Bósnia",
    "Qatar": "Catar",
    "Switzerland": "Suíça",
    "Brazil": "Brasil",
    "Morocco": "Marrocos",
    "Haiti": "Haiti",
    "Scotland": "Escócia",
    "USA": "Estados Unidos",
    "Paraguay": "Paraguai",
    "Australia": "Austrália",
    "Türkiye": "Turquia",
    "Germany": "Alemanha",
    "Curaçao": "Curaçau",
    "Ivory Coast": "Costa do Marfim",
    "Ecuador": "Equador",
    "Netherlands": "Holanda",
    "Japan": "Japão",
    "Sweden": "Suécia",
    "Tunisia": "Tunísia",
    "Belgium": "Bélgica",
    "Egypt": "Egito",
    "Iran": "Irã",
    "IR Iran": "Irã",
    "New Zealand": "Nova Zelândia",
    "Spain": "Espanha",
    "Cape Verde": "Cabo Verde",
    "Saudi Arabia": "Arábia Saudita",
    "Uruguay": "Uruguai",
    "France": "França",
    "Senegal": "Senegal",
    "Iraq": "Iraque",
    "Norway": "Noruega",
    "Argentina": "Argentina",
    "Algeria": "Argélia",
    "Austria": "Áustria",
    "Jordan": "Jordânia",
    "Portugal": "Portugal",
    "Congo DR": "República Democrática do Congo",
    "Uzbekistan": "Uzbequistão",
    "Colombia": "Colômbia",
    "England": "Inglaterra",
    "Croatia": "Croácia",
    "Ghana": "Gana",
    "Panama": "Panamá",
}

CITY_META: dict[str, tuple[str, str, str]] = {
    "Mexico City": ("Mexico City Stadium", "Cidade do México", "-06:00"),
    "Guadalajara": ("Estadio Guadalajara", "Guadalajara", "-06:00"),
    "Toronto": ("Toronto Stadium", "Toronto", "-04:00"),
    "Los Angeles": ("Los Angeles Stadium", "Los Angeles", "-07:00"),
    "Boston": ("Boston Stadium", "Foxborough", "-04:00"),
    "Vancouver": ("BC Place Vancouver", "Vancouver", "-07:00"),
    "East Rutherford, New Jersey (NYC)": (
        "New York New Jersey Stadium",
        "East Rutherford",
        "-04:00",
    ),
    "San Francisco": ("San Francisco Bay Area Stadium", "Santa Clara", "-07:00"),
    "Philadelphia": ("Philadelphia Stadium", "Filadélfia", "-04:00"),
    "Houston": ("Houston Stadium", "Houston", "-05:00"),
    "Dallas": ("Dallas Stadium", "Arlington", "-05:00"),
    "Monterrey": ("Estadio Monterrey", "Monterrey", "-06:00"),
    "Miami": ("Miami Stadium", "Miami Gardens", "-04:00"),
    "Atlanta": ("Atlanta Stadium", "Atlanta", "-04:00"),
    "Seattle": ("Seattle Stadium", "Seattle", "-07:00"),
    "Kansas City": ("Kansas City Stadium", "Kansas City", "-05:00"),
}

# Calendário local — FIFA (inside.fifa.com, 6 dez 2025) / worldtimezone.com
FIXTURES: list[tuple[str, str, str, str, str, str, int]] = [
    ("2026-06-11", "13:00", "Mexico City", "Mexico", "South Africa", "A", 1),
    ("2026-06-11", "20:00", "Guadalajara", "South Korea", "Czechia", "A", 1),
    ("2026-06-12", "15:00", "Toronto", "Canada", "Bosnia and Herzegovina", "B", 1),
    ("2026-06-12", "18:00", "Los Angeles", "USA", "Paraguay", "D", 1),
    ("2026-06-13", "21:00", "Boston", "Haiti", "Scotland", "C", 1),
    ("2026-06-13", "21:00", "Vancouver", "Australia", "Türkiye", "D", 1),
    ("2026-06-13", "18:00", "East Rutherford, New Jersey (NYC)", "Brazil", "Morocco", "C", 1),
    ("2026-06-13", "12:00", "San Francisco", "Qatar", "Switzerland", "B", 1),
    ("2026-06-14", "19:00", "Philadelphia", "Ivory Coast", "Ecuador", "E", 1),
    ("2026-06-14", "12:00", "Houston", "Germany", "Curaçao", "E", 1),
    ("2026-06-14", "15:00", "Dallas", "Netherlands", "Japan", "F", 1),
    ("2026-06-14", "20:00", "Monterrey", "Sweden", "Tunisia", "F", 1),
    ("2026-06-15", "18:00", "Miami", "Saudi Arabia", "Uruguay", "H", 1),
    ("2026-06-15", "12:00", "Atlanta", "Spain", "Cape Verde", "H", 1),
    ("2026-06-15", "18:00", "Los Angeles", "Iran", "New Zealand", "G", 1),
    ("2026-06-15", "12:00", "Seattle", "Belgium", "Egypt", "G", 1),
    ("2026-06-16", "15:00", "East Rutherford, New Jersey (NYC)", "France", "Senegal", "I", 1),
    ("2026-06-16", "18:00", "Boston", "Iraq", "Norway", "I", 1),
    ("2026-06-16", "20:00", "Kansas City", "Argentina", "Algeria", "J", 1),
    ("2026-06-16", "21:00", "San Francisco", "Austria", "Jordan", "J", 1),
    ("2026-06-17", "19:00", "Toronto", "Ghana", "Panama", "L", 1),
    ("2026-06-17", "15:00", "Dallas", "England", "Croatia", "L", 1),
    ("2026-06-17", "12:00", "Houston", "Portugal", "Congo DR", "K", 1),
    ("2026-06-17", "20:00", "Mexico City", "Uzbekistan", "Colombia", "K", 1),
    ("2026-06-18", "12:00", "Atlanta", "Czechia", "South Africa", "A", 2),
    ("2026-06-18", "12:00", "Los Angeles", "Switzerland", "Bosnia and Herzegovina", "B", 2),
    ("2026-06-18", "15:00", "Vancouver", "Canada", "Qatar", "B", 2),
    ("2026-06-18", "19:00", "Guadalajara", "Mexico", "South Korea", "A", 2),
    ("2026-06-19", "21:00", "Philadelphia", "Brazil", "Haiti", "C", 2),
    ("2026-06-19", "18:00", "Boston", "Scotland", "Morocco", "C", 2),
    ("2026-06-19", "20:00", "San Francisco", "Türkiye", "Paraguay", "D", 2),
    ("2026-06-19", "12:00", "Seattle", "USA", "Australia", "D", 2),
    ("2026-06-20", "16:00", "Toronto", "Germany", "Ivory Coast", "E", 2),
    ("2026-06-20", "19:00", "Kansas City", "Ecuador", "Curaçao", "E", 2),
    ("2026-06-20", "12:00", "Houston", "Netherlands", "Sweden", "F", 2),
    ("2026-06-20", "22:00", "Monterrey", "Tunisia", "Japan", "F", 2),
    ("2026-06-21", "18:00", "Miami", "Uruguay", "Cape Verde", "H", 2),
    ("2026-06-21", "12:00", "Atlanta", "Spain", "Saudi Arabia", "H", 2),
    ("2026-06-21", "12:00", "Los Angeles", "Belgium", "Iran", "G", 2),
    ("2026-06-21", "18:00", "Vancouver", "New Zealand", "Egypt", "G", 2),
    ("2026-06-22", "20:00", "East Rutherford, New Jersey (NYC)", "Norway", "Senegal", "I", 2),
    ("2026-06-22", "17:00", "Philadelphia", "France", "Iraq", "I", 2),
    ("2026-06-22", "12:00", "Dallas", "Argentina", "Austria", "J", 2),
    ("2026-06-22", "20:00", "San Francisco", "Jordan", "Algeria", "J", 2),
    ("2026-06-23", "16:00", "Boston", "England", "Ghana", "L", 2),
    ("2026-06-23", "19:00", "Toronto", "Panama", "Croatia", "L", 2),
    ("2026-06-23", "12:00", "Houston", "Portugal", "Uzbekistan", "K", 2),
    ("2026-06-23", "20:00", "Guadalajara", "Colombia", "Congo DR", "K", 2),
    ("2026-06-24", "18:00", "Miami", "Scotland", "Brazil", "C", 3),
    ("2026-06-24", "18:00", "Atlanta", "Morocco", "Haiti", "C", 3),
    ("2026-06-24", "12:00", "Vancouver", "Switzerland", "Canada", "B", 3),
    ("2026-06-24", "12:00", "Seattle", "Bosnia and Herzegovina", "Qatar", "B", 3),
    ("2026-06-24", "19:00", "Mexico City", "Czechia", "Mexico", "A", 3),
    ("2026-06-24", "19:00", "Monterrey", "South Africa", "South Korea", "A", 3),
    ("2026-06-25", "16:00", "Philadelphia", "Curaçao", "Ivory Coast", "E", 3),
    ("2026-06-25", "16:00", "East Rutherford, New Jersey (NYC)", "Ecuador", "Germany", "E", 3),
    ("2026-06-25", "18:00", "Dallas", "Japan", "Sweden", "F", 3),
    ("2026-06-25", "18:00", "Kansas City", "Tunisia", "Netherlands", "F", 3),
    ("2026-06-25", "19:00", "Los Angeles", "Türkiye", "USA", "D", 3),
    ("2026-06-25", "19:00", "San Francisco", "Paraguay", "Australia", "D", 3),
    ("2026-06-26", "15:00", "Boston", "Norway", "France", "I", 3),
    ("2026-06-26", "15:00", "Toronto", "Senegal", "Iraq", "I", 3),
    ("2026-06-26", "20:00", "Seattle", "Egypt", "Iran", "G", 3),
    ("2026-06-26", "20:00", "Vancouver", "New Zealand", "Belgium", "G", 3),
    ("2026-06-26", "19:00", "Houston", "Cape Verde", "Saudi Arabia", "H", 3),
    ("2026-06-26", "18:00", "Guadalajara", "Uruguay", "Spain", "H", 3),
    ("2026-06-27", "17:00", "East Rutherford, New Jersey (NYC)", "Panama", "England", "L", 3),
    ("2026-06-27", "17:00", "Philadelphia", "Croatia", "Ghana", "L", 3),
    ("2026-06-27", "21:00", "Kansas City", "Algeria", "Austria", "J", 3),
    ("2026-06-27", "21:00", "Dallas", "Jordan", "Argentina", "J", 3),
    ("2026-06-27", "19:30", "Miami", "Colombia", "Portugal", "K", 3),
    ("2026-06-27", "19:30", "Atlanta", "Congo DR", "Uzbekistan", "K", 3),
]


def pt_team(name_en: str) -> str:
    return TEAM_EN[name_en]


def slug_part(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
    return n[:12] or "team"


def match_id(group: str, round_no: int, home: str, away: str) -> str:
    return f"{group}-r{round_no}-{slug_part(home)}-{slug_part(away)}"


def kickoff_iso(date: str, time_local: str, tz: str) -> str:
    return f"{date}T{time_local}:00{tz}"


def build() -> dict:
    matches = []
    for date, time_local, city, home_en, away_en, group, round_no in FIXTURES:
        venue, city_pt, tz = CITY_META[city]
        home = pt_team(home_en)
        away = pt_team(away_en)
        matches.append(
            {
                "id": match_id(group, round_no, home, away),
                "home_team": home,
                "away_team": away,
                "group": group,
                "round": round_no,
                "phase": "group",
                "kickoff": kickoff_iso(date, time_local, tz),
                "venue": venue,
                "city": city_pt,
            }
        )

    return {
        "season": 2026,
        "competition": "Copa do Mundo FIFA 2026",
        "phase": "group",
        "groups": [{"id": gid, "teams": teams} for gid, teams in GROUPS],
        "matches": matches,
    }


def main() -> None:
    data = build()
    assert len(data["groups"]) == 12
    assert len(data["matches"]) == 72
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} — {len(data['groups'])} groups, {len(data['matches'])} matches")


if __name__ == "__main__":
    main()
