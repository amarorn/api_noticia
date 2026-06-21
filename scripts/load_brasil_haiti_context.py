#!/usr/bin/env python3
"""Carrega dados do relatório Brasil x Haiti e salva no match_context.

Uso:
    python scripts/load_brasil_haiti_context.py [event_id]

Se event_id não for fornecido, usa o ID do jogo na Superbet (se disponível)
ou cria um contexto genérico para teste.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Adiciona o projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.superbet.match_context_store import save_match_context


def build_brasil_haiti_context() -> dict:
    """Constrói contexto com dados do relatório Brasil x Haiti."""
    return {
        # Árbitro
        "referee_name": "Alejandro Hernandez Hernandez",
        "referee_nationality": "Espanha",
        "referee_card_lambda": 5.46,  # média de cartões/jogo na carreira
        "referee_foul_lambda": 23.89,  # média de faltas/jogo na La Liga
        "referee_penalty_rate": 0.40,  # 40% dos jogos têm pênalti
        "referee_red_card_rate": 0.15,  # 15% dos jogos têm vermelho
        "referee_profile": "punitivista",
        "referee_stats_source": "relatorio_analise",
        "referee_games_officiated": 322,
        
        # Contexto do jogo
        "match_name": "Brasil x Haiti",
        "competition": "Copa do Mundo 2026 - Grupo C",
        "match_date": "2026-06-19",
        "kickoff": "21:30",
        "venue": "Lincoln Financial Field, Filadelfia",
        "weather_temp_c": 25,
        "weather_humidity_pct": 75,
        "pitch_type": "sintetico",
        
        # H2H histórico
        "h2h_total_games": 3,
        "h2h_home_wins": 3,
        "h2h_draws": 0,
        "h2h_away_wins": 0,
        "h2h_home_goals_avg": 5.0,
        "h2h_away_goals_avg": 0.33,
        "h2h_last_result": "7-1",
        "h2h_last_date": "2016-06-08",
        "h2h_last_competition": "Copa America",
        
        # Situação do grupo
        "group_standings": {
            "group": "C",
            "after_round": 1,
            "teams": [
                {"pos": 1, "team": "Escocia", "pts": 3, "gp": 1, "w": 1, "d": 0, "l": 0, "gf": 1, "ga": 0},
                {"pos": 2, "team": "Marrocos", "pts": 1, "gp": 1, "w": 0, "d": 1, "l": 0, "gf": 1, "ga": 1},
                {"pos": 3, "team": "Brasil", "pts": 1, "gp": 1, "w": 0, "d": 1, "l": 0, "gf": 1, "ga": 1},
                {"pos": 4, "team": "Haiti", "pts": 0, "gp": 1, "w": 0, "d": 0, "l": 1, "gf": 0, "ga": 1},
            ]
        },
        
        # Stakes do jogo
        "brasil_stakes": {
            "if_win": "4 pts, próximo da classificação",
            "if_draw": "2 pts, precisa vencer Escócia na última",
            "if_lose": "1 pt, situação complicadíssima",
        },
        
        # Escalações prováveis
        "lineups": {
            "brasil": {
                "gk": "Alisson",
                "def": ["Danilo", "Marquinhos", "Gabriel Magalhaes", "Douglas Santos"],
                "mid": ["Casemiro", "Bruno Guimaraes", "Lucas Paqueta"],
                "fwd": ["Raphinha", "Vinicius Jr", "Igor Thiago"],
                "doubts": ["Neymar"],
            },
            "haiti": {
                "gk": "Johny Placide",
                "def": ["Carlens Arcus", "Ricardo Ade", "Hannes Delcroix", "Martin Experience"],
                "mid": ["Jean-Ricner Bellegarde", "Danley Jean Jacques"],
                "fwd": ["Ruben Providence", "Louicius Deedson", "Wilson Isidor", "Frantzdy Pierrot"],
            }
        },
        
        # Análise textual (para futuro LLM)
        "analysis_summary": (
            "Brasil é MASSIVO favorito. Histórico H2H: 3 vitórias em 3 jogos, "
            "15 gols marcados vs 1 sofrido. Últimos confrontos: 7-1 (2016) e 6-0 (2004). "
            "Árbitro Hernandez é punitivista (5.46 cartões/jogo). "
            "Haiti tem problema de finalização (0 gols em 15 chutes vs Escócia)."
        ),
    }


def main() -> None:
    event_id = int(sys.argv[1]) if len(sys.argv) > 1 else 999999  # ID de teste
    
    context = build_brasil_haiti_context()
    path = save_match_context(event_id, context)
    
    print(f"✅ Contexto salvo para event_id={event_id}")
    print(f"   Path: {path}")
    print(f"\n📊 Dados do árbitro:")
    print(f"   Nome: {context['referee_name']}")
    print(f"   Perfil: {context['referee_profile']}")
    print(f"   Cartões/jogo: {context['referee_card_lambda']}")
    print(f"   Faltas/jogo: {context['referee_foul_lambda']}")
    print(f"   Pênaltis/jogo: {context['referee_penalty_rate']}")
    print(f"   Vermelhos/jogo: {context['referee_red_card_rate']}")
    print(f"\n⚽ H2H:")
    print(f"   Jogos: {context['h2h_total_games']}")
    print(f"   Vitórias Brasil: {context['h2h_home_wins']}")
    print(f"   Média gols Brasil: {context['h2h_home_goals_avg']}")
    print(f"   Último: {context['h2h_last_result']} ({context['h2h_last_date']})")
    
    print(f"\n💡 Para testar:")
    print(f"   curl -H 'X-API-Key: dev-key-123' \\")
    print(f"     'http://localhost:8000/worldcup/superbet/live/{event_id}/advice?fast=true' \\")
    print(f"     | python3 -m json.tool | grep -A5 'referee'")


if __name__ == "__main__":
    main()
