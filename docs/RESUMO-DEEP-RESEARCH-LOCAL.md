# Deep Research Local - Resumo de Implementação

## Problema
A aba "Deep Research" mostrava erro quando as APIs externas (Gemini, Moonshot) estavam indisponíveis:
- Gemini: HTTP 404 (modelo não encontrado)
- Moonshot: HTTP 429 (quota esgotada)
- Resultado: "Síntese IA temporariamente indisponível"

## Solução
Criamos uma **síntese local** que usa os dados do nosso modelo + contexto pré-jogo (relatório TXT) para gerar análise estruturada sem depender de APIs externas.

## Arquivos Criados/Modificados

### Backend
| Arquivo | Descrição | Linhas |
|---------|-----------|--------|
| `models/wc_local_synthesis.py` | Gerador de síntese local | 320 |
| `api/main.py` | Integração no endpoint `/worldcup/pregame/research` | +20 |
| `tests/test_wc_local_synthesis.py` | 16 testes unitários | 200 |

### Frontend
| Arquivo | Descrição |
|---------|-----------|
| `frontend/src/presentation/pages/PreGameAnalysisPage.tsx` | Mensagem atualizada: "Análise Local Ativa" |

### Dados (existente)
| Arquivo | Uso |
|---------|-----|
| `data/lake/live_contexts/{event_id}.json` | Contexto pré-jogo (árbitro, H2H, escalações, stakes) |

## Como funciona

### Quando APIs disponíveis
```
Gemini → Síntese IA completa ✅
```

### Quando APIs INDISPONÍVEIS (novo)
```
Modelo WC (probabilidades) +
Match Context (relatório TXT: árbitro, H2H, escalações, stakes) +
Regras de negócio (picks, fatores, riscos)
  ↓
Síntese Local (estrutura idêntica à IA)
  ↓
Frontend renderiza normalmente
```

## Dados usados na síntese local

| Campo | Fonte | Exemplo (Brasil x Haiti) |
|-------|-------|--------------------------|
| **Resumo** | Modelo + Contexto | "Modelo prevê 1 com 72% confiança..." |
| **Favorito** | Modelo | Brasil (Alta confiança) |
| **Picks** | Modelo (Kelly, EV) | Vitória Brasil, Over 2.5, BTTS |
| **Fatores** | Contexto + Modelo | Dominância H2H (3/3), Árbitro punitivista |
| **Riscos** | Contexto + Modelo | Gramado sintético, Neymar lesionado |
| **Escalações** | Contexto | Alisson, Marquinhos, Vini Jr... |
| **Árbitro** | Contexto | Hernandez (5.46 cartões/jogo) |
| **Mercados** | Modelo | 1X2, Over/Under, BTTS |
| **Placar** | Modelo (Poisson) | 3x0 (25% prob) |

## Testes
- **16 testes** em `test_wc_local_synthesis.py` — todos passando ✅
- **72 testes** totais (referee + local + combo) — todos passando ✅

## Uso

### 1. Carregar contexto (se tiver relatório TXT)
```bash
python3 scripts/load_brasil_haiti_context.py 13127506
```

### 2. Chamar Deep Research
```bash
curl "http://localhost:8000/worldcup/pregame/research?home=Brasil&away=Haiti&phase=group"
```

### 3. Resultado
- Se APIs OK: síntese Gemini/Moonshot
- Se APIs falham: **síntese local** com dados do modelo + contexto

## Próximos passos
1. **Painel de árbitro** no frontend (mercados de cartões/faltas)
2. **Integrar mais dados do relatório**: clima, stakes do grupo, forma recente
3. **Melhorar escalações**: usar dados FIFA/Sofascore em tempo real
4. **Cache inteligente**: salvar síntese local quando APIs falham
