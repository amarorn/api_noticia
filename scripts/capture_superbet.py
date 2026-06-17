#!/usr/bin/env python3
"""Script para capturar apostas abertas da Superbet via clipboard.

Uso:
    1. Abra a página "Minhas Apostas" da Superbet no navegador
    2. Copie o texto do card da aposta (Ctrl+C ou Cmd+C)
    3. Rode: ./scripts/capture_superbet.py
    4. O script lê a área de transferência, parseia e envia para a API
    5. A aposta aparece no painel ao vivo automaticamente

Dependências:
    pip install pyperclip requests
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    import pyperclip
    import requests
except ImportError:
    print("Instale as dependências: pip install pyperclip requests")
    sys.exit(1)

API_BASE = "http://127.0.0.1:8000"


def parse_clipboard(text: str) -> dict | None:
    """Extrai dados da aposta a partir do texto copiado da Superbet."""
    from models.bet_pick_classify import classify_superbet_pick

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None

    event_line = lines[0]
    teams = None
    for sep in ("·", "—", " - ", " vs ", " x "):
        if sep in event_line:
            parts = event_line.split(sep)
            if len(parts) >= 2:
                teams = (parts[0].strip(), parts[1].strip())
                break

    if not teams:
        return None

    picks = []
    import re

    for ln in lines:
        m = re.match(r"(.+?)\s*[—–-]\s*(.+?)(?:\s*@\s*[\d.,]+)?$", ln.strip())
        if m:
            classified = classify_superbet_pick(
                m.group(1).strip(),
                m.group(2).strip(),
                home_team=teams[0],
                away_team=teams[1],
            )
            pick = {
                "market": classified["market"],
                "outcome": classified["outcome"],
            }
            if classified.get("target_value"):
                pick["target_value"] = classified["target_value"]
            picks.append(pick)
            continue
        ln_lower = ln.lower()
        if "criar aposta" in ln_lower:
            picks.append({"market": "combo", "outcome": "combo"})

    # Extrair valor apostado
    stake = 0.0
    for ln in lines:
        m = re.search(r"APOSTA\s*([\d.,]+)", ln)
        if m:
            stake = float(m.group(1).replace(".", "").replace(",", "."))
            break

    # Extrair odd total
    total_odd = 0.0
    for ln in lines:
        m = re.search(r"ODDS\s*TOTAIS\s*([\d.,]+)", ln)
        if m:
            total_odd = float(m.group(1).replace(",", "."))
            break
        m = re.search(r"@\s*([\d.,]+)", ln)
        if m:
            total_odd = float(m.group(1).replace(",", "."))

    # Extrair ticket code (ex: 892P-1YINSZ)
    ticket_code = None
    for ln in lines:
        m = re.search(r"\b([A-Z0-9]{3,}-?[A-Z0-9]{5,})\b", ln)
        if m and not re.search(r"ODDS|APOSTA|Ganho|R\\$", ln):
            ticket_code = m.group(1)
            break

    # Extrair ganho potencial
    potential_return = 0.0
    for ln in lines:
        m = re.search(r"GANHO\s+POTENCIAL\s*R?\$?\s*([\d.,]+)", ln, re.I)
        if m:
            potential_return = float(m.group(1).replace(".", "").replace(",", "."))
            break
        m = re.search(r"Retorno\s*R?\$?\s*([\d.,]+)", ln, re.I)
        if m:
            potential_return = float(m.group(1).replace(".", "").replace(",", "."))
            break

    if not picks or stake <= 0 or total_odd <= 1:
        return None

    return {
        "event_name": event_line,
        "home_team": teams[0],
        "away_team": teams[1],
        "picks": picks,
        "stake": stake,
        "odds_placed": total_odd,
        "potential_return": potential_return if potential_return > 0 else round(stake * total_odd, 2),
        "ticket_code": ticket_code,
        "source": "clipboard_capture",
    }


def send_to_api(payload: dict, api_key: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    resp = requests.post(
        f"{API_BASE}/user/open-bets",
        json=payload,
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura aposta da Superbet via clipboard")
    parser.add_argument("--api-key", default=None, help="API key para autenticação")
    parser.add_argument("--text", default=None, help="Texto da aposta (em vez de clipboard)")
    parser.add_argument("--paste", action="store_true", help="Lê JSON do clipboard e envia direto (modo DevTools)")
    args = parser.parse_args()

    if args.paste:
        raw = pyperclip.paste()
        try:
            payload_list = json.loads(raw)
            if not isinstance(payload_list, list):
                payload_list = [payload_list]
        except json.JSONDecodeError:
            print("❌ JSON inválido no clipboard.")
            sys.exit(1)
        for payload in payload_list:
            payload.setdefault("source", "clipboard_paste")
            try:
                result = send_to_api(payload, api_key=args.api_key)
                print(f"🎉 Enviado: {payload.get('event_name')} — ID {result.get('id')}")
            except requests.HTTPError as e:
                print(f"❌ Erro: {e}")
        return

    text = args.text or pyperclip.paste()
    if not text or len(text) < 20:
        print("❌ Área de transferência vazia ou texto muito curto.")
        print("   Copie o card da aposta da Superbet e tente novamente.")
        sys.exit(1)

    print("🔍 Analisando texto copiado...")
    payload = parse_clipboard(text)
    if not payload:
        print("❌ Não consegui extrair dados válidos.")
        print("   Certifique-se de copiar o card completo: evento, mercado, valor e odd.")
        sys.exit(1)

    print(f"✅ Aposta identificada: {payload['home_team']} × {payload['away_team']}")
    print(f"   Mercados: {', '.join(p['market'] for p in payload['picks'])}")
    print(f"   Stake: R$ {payload['stake']:.2f} · Odd: {payload['odds_placed']:.2f}")
    print(f"   Ganho potencial: R$ {payload['potential_return']:.2f}")
    print(f"   Ticket: {payload.get('ticket_code') or 'não identificado'}")
    print("📡 Enviando para a API...")

    try:
        result = send_to_api(payload, api_key=args.api_key)
        print(f"🎉 Aposta cadastrada! ID: {result.get('id')}")
        print("   Aposta aparece no painel: /ao-vivo")
    except requests.HTTPError as e:
        print(f"❌ Erro da API: {e}")
        try:
            print(e.response.json().get("detail", ""))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
