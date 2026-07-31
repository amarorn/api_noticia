TEAM_ALIASES: dict[str, str] = {
    "SC Internacional": "Internacional",
    "Internacional": "Internacional",
    "EC Bahia": "Bahia",
    "Bahia": "Bahia",
    "Fluminense FC": "Fluminense",
    "Fluminense": "Fluminense",
    "RB Bragantino": "Bragantino",
    "Red Bull Bragantino": "Bragantino",
    "Bragantino": "Bragantino",
    "São Paulo FC": "São Paulo",
    "São Paulo": "São Paulo",
    "Fortaleza EC": "Fortaleza",
    "Fortaleza": "Fortaleza",
    "CR Vasco da Gama": "Vasco",
    "Vasco da Gama": "Vasco",
    "Vasco": "Vasco",
    "Grêmio FBPA": "Grêmio",
    "Grêmio": "Grêmio",
    "SC Corinthians Paulista": "Corinthians",
    "Corinthians": "Corinthians",
    "CA Mineiro": "Atlético-MG",
    "Atlético Mineiro": "Atlético-MG",
    "Atlético-MG": "Atlético-MG",
    "CA Paranaense": "Athletico-PR",
    "Athletico Paranaense": "Athletico-PR",
    "Athletico-PR": "Athletico-PR",
    "Cuiabá EC": "Cuiabá",
    "Cuiabá": "Cuiabá",
    "AC Goianiense": "Goiás",
    "Goiás EC": "Goiás",
    "Goiás": "Goiás",
    "CR Flamengo": "Flamengo",
    "Flamengo": "Flamengo",
    "Cruzeiro EC": "Cruzeiro",
    "Cruzeiro": "Cruzeiro",
    "Botafogo FR": "Botafogo",
    "Botafogo": "Botafogo",
    "EC Vitória": "Vitória",
    "Vitória": "Vitória",
    "SE Palmeiras": "Palmeiras",
    "Palmeiras": "Palmeiras",
    "Santos FC": "Santos",
    "Santos": "Santos",
    "EC Juventude": "Juventude",
    "Juventude": "Juventude",
    "Criciúma EC": "Criciúma",
    "Criciúma": "Criciúma",
    "América FC": "América-MG",
    "América Mineiro": "América-MG",
    "América-MG": "América-MG",
    "Sport Recife PE": "Sport",
    "Sport Club do Recife": "Sport",
    "Sport Recife": "Sport",
    "Sport": "Sport",
    "Ceará SC": "Ceará",
    "Ceará": "Ceará",
    "Avaí FC": "Avaí",
    "Avaí": "Avaí",
    "Coritiba FC": "Coritiba",
    "Coritiba": "Coritiba",
}


def normalize_team(name: str) -> str:
    cleaned = " ".join(name.split())
    return TEAM_ALIASES.get(cleaned, cleaned)


BRAZILIAN_TEAMS: list[str] = sorted(set(TEAM_ALIASES.values()))

TEAM_NICKNAMES: dict[str, list[str]] = {
    "Flamengo": ["mengão", "mengao", "fla ", " fla", "rubro-negro"],
    "Palmeiras": ["verdão", "verdao", "porco", "alviverde"],
    "Corinthians": ["timão", "timao", "fiel"],
    "São Paulo": ["tricolor", "spfc", "são paulo fc"],
    "Santos": ["peixe", "santástico"],
    "Grêmio": ["tricolor gaúcho", "gremio", "imortal"],
    "Internacional": ["colorado", "inter "],
    "Atlético-MG": ["galo", "atletico-mg", "atlético mineiro"],
    "Cruzeiro": ["raposa", "cabuloso"],
    "Botafogo": ["fogão", "fogao", "glorioso"],
    "Vasco": ["gigante da colina", "vascão"],
    "Fluminense": ["tricolor carioca", "flu "],
    "Bahia": ["tricolor de aço", "esquadrão"],
    "Sport": ["leão", "leao pernambucano"],
    "Fortaleza": ["leão do pici", "tricolor de aço cearense"],
    "Athletico-PR": ["furacão", "furacao", "athletico"],
    "Bragantino": ["massa bruta", "red bull"],
}


def teams_from_text(text: str) -> list[str]:
    """Extrai times canônicos por nome oficial, alias ou apelido (ordem: apelidos longos primeiro)."""
    text_lower = text.lower()
    found: list[str] = []
    seen: set[str] = set()

    nickname_hits: list[tuple[int, str]] = []
    for team, nicknames in TEAM_NICKNAMES.items():
        for nick in nicknames:
            if nick.strip() and nick in text_lower:
                nickname_hits.append((len(nick), team))
    for _, team in sorted(nickname_hits, key=lambda x: -x[0]):
        if team not in seen:
            seen.add(team)
            found.append(team)

    for team in sorted(BRAZILIAN_TEAMS, key=len, reverse=True):
        if team.lower() in text_lower and team not in seen:
            seen.add(team)
            found.append(team)

    return found


def article_mentions_team(teams_mentioned, team: str) -> bool:
    if teams_mentioned is None:
        return False
    if hasattr(teams_mentioned, "tolist"):
        teams_mentioned = teams_mentioned.tolist()
    return team in teams_mentioned
