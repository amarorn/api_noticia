# Módulo de Árbitro In-Play - Resumo de Implementação

## O que foi implementado

### 1. `models/wc_referee_inplay.py` (357 linhas)
Módulo principal que integra dados do árbitro ao modelo in-play.

**Funcionalidades:**
- `RefereeProfile` dataclass: perfil estatístico do árbitro (cartões, faltas, pênaltis, vermelhos)
- Auto-classificação do perfil: punitivista / equilibrado / pacificador
- `parse_referee_from_match_context()`: extrai dados do match_context (formato flat ou aninhado)
- `referee_card_market_probs()`: calcula probabilidades para mercados de cartões ao vivo
  - Over 3.5/4.5/5.5/6.5 cartões amarelos
  - Cartão vermelho
  - Pênalti
  - Over 20.5/25.5/30.5 faltas
- Ajustes dinâmicos por minuto (aceleração punitivista no 2º tempo)
- Multiplicadores por perfil: punitivista +35% cartões, pacificador -22%

**Exemplo de uso:**
```python
from models.wc_referee_inplay import RefereeProfile, referee_card_market_probs

r = RefereeProfile(
    "Hernandez", card_lambda=5.46, foul_lambda=23.89,
    penalty_rate=0.40, red_card_rate=0.15, profile="punitivista"
)
probs = referee_card_market_probs(r, minute=0, match_minutes=90)
# over_4_5_yellow: 0.858
# red_card_yes: 0.210
# penalty_yes: 0.500
```

### 2. Integração em `ingest/superbet/advice.py`
- Carrega `referee_profile` do `match_context`
- Calcula `referee_markets` e adiciona ao `inplay_dict`
- Mercados de cartões agora aparecem no payload da API

### 3. `scripts/load_brasil_haiti_context.py`
Script para carregar dados do relatório Brasil x Haiti:
```bash
python3 scripts/load_brasil_haiti_context.py 13127506
```

Salva em `data/lake/live_contexts/{event_id}.json` com:
- Dados do árbitro Hernandez (5.46 cartões/jogo, punitivista)
- H2H histórico (Brasil 3x0, média 5 gols/jogo)
- Situação do grupo C
- Escalações prováveis
- Condições do jogo (Filadelfia, gramado sintético)

### 4. `tests/test_wc_referee_inplay.py` (24 testes)
Cobertura completa: criação, parsing, classificação, mercados, ajustes por minuto.

## Resultados do Brasil x Haiti

Com os dados do relatório, o modelo calcula:

| Mercado | Probabilidade |
|---------|--------------|
| Over 3.5 cartões | 93.6% |
| Over 4.5 cartões | 85.8% |
| Over 5.5 cartões | 74.4% |
| Cartão vermelho | 21.0% |
| Pênalti | 50.0% |
| Over 20.5 faltas | 91.3% |

## Próximos passos sugeridos

1. **Frontend**: Adicionar painel de "Mercados de Disciplina" na tela Ao Vivo
2. **Mais dados do relatório**: Integrar H2H histórico como ajuste no λ (força de ataque)
3. **Clima/gramado**: Usar dados de temperatura/umidade do contexto para ajustar λ
4. **Escalações**: Usar escalações confirmadas para ajustar força ofensiva/defensiva
5. **Stakes do grupo**: Ajustar λ baseado na importância do jogo (precisa vencer vs já classificado)
