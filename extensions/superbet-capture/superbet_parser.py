"""
Extrai apostas abertas do DOM da Superbet (área "Minhas Apostas").

Como o DOM da Superbet muda, o parser usa heurísticas resilientes:
- Busca cards por atributos/texto (AO VIVO, R$, CRIAR APOSTA)
- Extrai evento, mercados, stake, odd, cash-out
- Normaliza mercados para o formato da nossa API
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Permite importar models/ quando rodado a partir da raiz do projeto.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _classify_pick(market_raw: str, pick_raw: str, *, home_team: str = "", away_team: str = "") -> dict:
    from models.bet_pick_classify import classify_superbet_pick

    return classify_superbet_pick(
        market_raw,
        pick_raw,
        home_team=home_team,
        away_team=away_team,
    )


@dataclass
class ParsedPick:
    raw_text: str
    market: str | None = None
    outcome: str | None = None
    target_value: str | None = None


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
    status: str
    source_text: str
    captured_at: str = field(default_factory=lambda: __import__("datetime", fromlist=["datetime"]).datetime.now().isoformat())


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


def _parse_market_line(
    line: str,
    *,
    home_team: str = "",
    away_team: str = "",
) -> ParsedPick | None:
    """Parseia uma linha de mercado no formato ``Mercado — Palpite`` ou ``Mercado — Palpite @ odd``."""
    m = re.match(r"(.+?)\s*[—–-]\s*(.+?)(?:\s*@\s*[\d.,]+)?$", line.strip())
    if not m:
        return None
    market_raw, pick_raw = m.group(1).strip(), m.group(2).strip()
    classified = _classify_pick(
        market_raw,
        pick_raw,
        home_team=home_team,
        away_team=away_team,
    )
    return ParsedPick(
        raw_text=line,
        market=classified["market"],
        outcome=classified["outcome"],
        target_value=classified.get("target_value"),
    )


def _parse_markets(description: str, *, home_team: str = "", away_team: str = "") -> list[ParsedPick]:
    """Parseia a descrição da aposta em um ou mais picks."""
    picks: list[ParsedPick] = []
    for line in [ln.strip() for ln in description.split("\n") if ln.strip()]:
        parsed = _parse_market_line(line, home_team=home_team, away_team=away_team)
        if parsed:
            picks.append(parsed)
            continue
        if re.search(r"CRIAR\s+APOSTA", line, re.IGNORECASE):
            picks.append(ParsedPick(raw_text=line, market="combo", outcome="combo"))
        else:
            picks.append(ParsedPick(raw_text=line))
    return picks


def parse_superbet_open_bets(html_text: str) -> list[ParsedBet]:
    """Parser genérico sobre HTML/texto da página Minhas Apostas."""
    bets: list[ParsedBet] = []

    blocks = re.split(r'(?=\b(?:AO VIVO|ÚNICO|Encerrado|Concluído)\b)', html_text, flags=re.IGNORECASE)

    for block in blocks:
        if not re.search(r"AO VIVO|aberta|pendente", block, re.IGNORECASE):
            continue

        event_match = re.search(r"^\s*([\w\s()]+[·\-–—][\w\s()]+)", block, re.MULTILINE)
        event_name = event_match.group(1).strip() if event_match else "Desconhecido"
        home, away = _extract_teams(event_name)

        desc_lines = []
        for line in block.splitlines():
            if re.search(
                r"CRIAR APOSTA|Total de Gols|Ambas|Resultado|Próximo gol|Handicap|Vence|Tempo",
                line,
                re.IGNORECASE,
            ):
                desc_lines.append(line.strip())
        description = "\n".join(desc_lines)

        stake_match = re.search(r"APOSTA\s*([\d.,\s]+R\$|R\$[\d.,\s]+)", block, re.IGNORECASE)
        stake = _normalize_money(stake_match.group(1)) if stake_match else 0.0

        odd_match = re.search(r"ODDS\s*TOTAIS\s*([\d.,]+)", block, re.IGNORECASE)
        total_odd = float(odd_match.group(1).replace(",", ".")) if odd_match else 0.0

        cashout_match = re.search(r"Cashout\s+([\d.,]+)\s*R\$", block, re.IGNORECASE)
        cashout = float(cashout_match.group(1).replace(",", ".")) if cashout_match else None

        picks = (
            _parse_markets(description, home_team=home or "", away_team=away or "")
            if description
            else []
        )

        bets.append(
            ParsedBet(
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
            )
        )

    return bets
