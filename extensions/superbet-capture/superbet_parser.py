"""
Extrai apostas abertas do DOM da Superbet (área "Minhas Apostas").

Como o DOM da Superbet muda, o parser usa heurísticas resilientes:
- Busca cards por atributos/texto (AO VIVO, R$, CRIAR APOSTA)
- Extrai evento, mercados, stake, odd, cash-out
- Normaliza mercados para o formato da nossa API
"""

import re
from dataclasses import dataclass, field


@dataclass
class ParsedPick:
    raw_text: str
    market: str | None = None  # h2h | over_2_5 | btts | btts_any_half | combo_over_btts | ...
    outcome: str | None = None  # 1 | X | 2 | yes | no | home | away | "over_2.5" | ...
    target_value: str | None = None  # "2" na odd total. Precisei verificar se estava no campo errado.


@dataclass
class ParsedBet:
    event_id: int | None
    event_name: str
    home_team: str | None
    away_team: str | None
    picks: list[ParsedPick]
    stake: float
    total_odd: float
    offered_cashout: float | None
    is_live: bool
    status: str  # "open" | "won" | "lost" | "void"
    source_text: str  # texto bruto para debug
    captured_at: str = field(default_factory=lambda: __import__("datetime", fromlist=["datetime"]).datetime.now().isoformat())


_MARKET_PATTERNS = [
    # (regex do texto bruto, market_key, outcome_extraction)
    (r"Resultado Final\s*—\s*([1X2])", "h2h", lambda m: m.group(1)),
    (r"Total de Gols:\s*(Mais|Menos) de ([\d.]+)", "over_{value}", lambda m: f"{'yes' if m.group(1) == 'Mais' else 'no'}"),
    (r"Total de Gols\s*—\s*([\d.]+)", "total_gols", lambda m: m.group(1)),
    (r"Ambas as Equipes Marcam:\s*(Sim|Não)", "btts", lambda m: "yes" if m.group(1) in ("Sim", "Sim") else "no"),
    (r"Ambas as Equipes Marcam em Algum dos Tempos:\s*(Sim|Não)", "btts_any_half", lambda m: "yes" if m.group(1) == "Sim" else "no"),
    (r"([\w\s()]+) - Vence", "h2h", lambda m: "home" if "mandante" in m.group(1).lower() else "away"),
    (r"Próximo\s+gol\s*—?\s*([\w\s()]+)", "next_goal", lambda m: "home" if m.group(1).lower() in ("1", "casa", "home") else "away"),
    (r"Handicap\s+Asiático", "asian_handicap", lambda m: None),
    (r"CRIAR\s+APOSTA", "combo", lambda m: "combo"),
    (r"([\w\s]+)\s*@\s*[\d.,]+", "generic", lambda m: None),
]


def _extract_teams(event_name: str) -> tuple[str | None, str | None]:
    """Extrai mandante e visitante do nome do evento."""
    for sep in (" — ", " - ", " vs ", " x ", " · "):
        if sep in event_name:
            parts = event_name.split(sep)
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()
    return None, None


def _normalize_money(text: str) -> float:
    """Converte '5,00 R$' ou 'R$ 5.00' → 5.0"""
    t = text.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    m = re.search(r"[\d.]+", t)
    return float(m.group()) if m else 0.0


def _extract_odd(text: str) -> float:
    """Extrai odd de texto como '@ 1.12' ou '1.12'."""
    m = re.search(r"@?\s*([\d.,]+)", text)
    if not m:
        return 0.0
    t = m.group(1).replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def _parse_markets(description: str) -> list[ParsedPick]:
    """Parseia a descrição da aposta em um ou mais picks."""
    picks: list[ParsedPick] = []

    # 1. Detectar combos (várias linhas separadas)
    lines = [ln.strip() for ln in description.split("\n") if ln.strip()]

    for line in lines:
        matched = False
        for pattern, market_template, outcome_fn in _MARKET_PATTERNS:
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                outcome = outcome_fn(m)
                target = None
                if "{value}" in market_template:
                    # extrair valor numérico, se houver
                    vm = re.search(r"([\d.]+)", line)
                    target = vm.group(1) if vm else None
                    market = market_template.replace("{value}", target or "0")
                else:
                    market = market_template
                picks.append(ParsedPick(raw_text=line, market=market, outcome=outcome, target_value=target))
                matched = True
                break
        if not matched:
            picks.append(ParsedPick(raw_text=line))

    return picks


def parse_superbet_open_bets(html_text: str) -> list[ParsedBet]:
    """Parser genérico sobre HTML/texto da página Minhas Apostas."""
    bets: list[ParsedBet] = []

    # Heurística: separar por cards que contenham "AO VIVO" ou "ÚNICO"
    # A Superbet usa cards separados visualmente
    blocks = re.split(r'(?=\b(?:AO VIVO|ÚNICO|Encerrado|Concluído)\b)', html_text, flags=re.IGNORECASE)

    for block in blocks:
        if not re.search(r'AO VIVO|aberta|pendente', block, re.IGNORECASE):
            continue  # Só apostas abertas ao vivo

        # Extrair nome do evento (primeira linha com time vs time)
        event_match = re.search(r'^\s*([\w\s()]+[·\-–—][\w\s()]+)', block, re.MULTILINE)
        event_name = event_match.group(1).strip() if event_match else "Desconhecido"
        home, away = _extract_teams(event_name)

        # Extrair descrição do mercado (linhas após evento, antes de valores)
        desc_lines = []
        for line in block.splitlines():
            if re.search(r'CRIAR APOSTA|Total de Gols|Ambas|Resultado|Próximo gol|Handicap|Vence', line, re.IGNORECASE):
                desc_lines.append(line.strip())
        description = "\n".join(desc_lines)

        # Extrair stake
        stake_match = re.search(r'APOSTA\s*([\d.,\s]+R\$|R\$[\d.,\s]+)', block, re.IGNORECASE)
        stake = _normalize_money(stake_match.group(1)) if stake_match else 0.0

        # Extrair odd total
        odd_match = re.search(r'ODDS\s*TOTAIS\s*([\d.,]+)', block, re.IGNORECASE)
        total_odd = float(odd_match.group(1).replace(",", ".")) if odd_match else 0.0

        # Extrair cash-out
        cashout_match = re.search(r'Cashout\s+([\d.,]+)\s*R\$', block, re.IGNORECASE)
        cashout = float(cashout_match.group(1).replace(",", ".")) if cashout_match else None

        picks = _parse_markets(description) if description else []

        bets.append(ParsedBet(
            event_id=None,
            event_name=event_name,
            home_team=home,
            away_team=away,
            picks=picks,
            stake=stake,
            total_odd=total_odd,
            offered_cashout=cashout,
            is_live=True,
            status="open",
            source_text=block[:500],
        ))

    return bets
