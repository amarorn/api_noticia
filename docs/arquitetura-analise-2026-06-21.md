# Análise Arquitetural — api_noticia (Bolão AI)

> Data: 2026-06-21
> Objetivo: Organizar o raciocínio do projeto e identificar o que funciona vs. o que está quebrado

---

## 1. Visão Geral do Projeto

**Bolão AI** é um sistema de predição de resultados de futebol com duas modalidades principais:

### 1.1 Pré-Jogo (Pre-Match)
- **Input**: Dois times + data/hora do jogo
- **Output**: Probabilidades 1/X/2, over/under, BTTS, handicap, escalações, análise textual
- **Fontes**: Dados históricos WC, FIFA rankings, Sofascore stats, KXL baselines
- **Modelos**: Poisson, Dixon-Coles, Logistic Regression, KXL Collision, Ensemble

### 1.2 Ao Vivo (In-Play / Live)
- **Input**: Evento Superbet ao vivo (placar, minuto, odds, stats)
- **Output**: Probabilidades atualizadas, recomendações de aporte/cash-out, mercados de 2º tempo
- **Fontes**: Superbet API (SSE), ScoreAlarm (timeline, stats), Sofascore (live stats)
- **Modelos**: Poisson MC com Bayesian update, momentum, NHPP, ensemble Hawkes+GBM

---

## 2. Arquitetura de Dados (Medalhão)

```
┌─────────────────────────────────────────────────────────────────┐
│                        FONTES EXTERNAS                          │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│  RSS News   │  FIFA API   │ Sofascore   │  Superbet API (SSE)  │
│  (7 fontes) │  (rankings) │ (stats xG) │  (odds ao vivo)      │
└──────┬──────┴──────┬──────┴──────┬──────┴───────────┬───────────┘
       │             │             │                  │
       ▼             ▼             ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BRONZE (raw)                              │
│  - Parquet particionado por source/year/month/day                  │
│  - JSON snapshots (superbet events, FIFA cache, friendlies)      │
│  - TXT reports (match context manual)                              │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SILVER (clean)                            │
│  - Deduplicação, normalização de times, sentiment analysis       │
│  - Features: Elo, forma, H2H, xG, lesões, escalações            │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                          GOLD (features)                          │
│  - Feature vectors para modelos ML                               │
│  - WcMatchFeatures: 40+ features por jogo                        │
│  - Bet advice, strategy, EV/Kelly calculations                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Modelos — O Que Realmente Existe

### 3.1 Modelos Pré-Jogo (Funcionando)

| Modelo | Arquivo | Status | Descrição |
|--------|---------|--------|-----------|
| **Poisson WC** | `poisson_wc.py` | ✅ | Força ataque/defesa com meia-vida temporal |
| **Dixon-Coles** | `dixon_coles_wc.py` | ✅ | Ajuste ρ para jogos de baixo placar |
| **Logistic Regression** | `logistic_wc.py` | ✅ | Calibrada com CalibratedClassifierCV |
| **Collaborative Ensemble** | `wc_collaborative.py` | ✅ | Blend Dixon-Coles + Logistic (otimizado Brier) |
| **Draw Model** | `wc_draw_model.py` | ✅ | Classificador dedicado para empate |
| **KXL Collision** | `pipelines/wc_kxl_collision.py` | ✅ | Motor tático (Energy × Space × Time) |
| **Predictor** | `wc_predictor.py` | ✅ | Pipeline completo: treino + inferência |
| **Match Simulator** | `wc_match_simulator.py` | ✅ | Ensemble + FIFA + Sofascore + KXL |
| **Corners** | `corners_predictor.py` | ✅ | Poisson para escanteios |
| **Handicap** | `wc_handicap.py` | ✅ | Monte Carlo + EV/Kelly por linha |

### 3.2 Modelos Ao Vivo (Funcionando)

| Modelo | Arquivo | Status | Descrição |
|--------|---------|--------|-----------|
| **In-Play Poisson MC** | `wc_inplay.py` | ✅ | Simulação Monte Carlo condicionada ao placar/minuto |
| **Bayesian Update** | `wc_inplay.py` | ✅ | Gamma-Poisson conjugada com gols observados |
| **NHPP** | `pipelines/wc_intensity_profile.py` | ✅ | Intensidade não-homogênea por período |
| **Market Shrinkage** | `wc_market_shrinkage.py` | ✅ | Mistura λ modelo com λ implícito do mercado |
| **Momentum** | `wc_live_momentum.py` | ✅ | Eventos (gol, cartão, corner) ajustam λ |
| **H2H Adjust** | `wc_inplay_h2h_adjust.py` | ✅ NOVO | Comeback boost baseado em histórico H2H |
| **Referee Markets** | `wc_referee_inplay.py` | ✅ NOVO | Probabilidades de cartões/faltas/pênaltis |
| **Local Synthesis** | `wc_local_synthesis.py` | ✅ NOVO | Fallback quando APIs externas falham |
| **Ensemble Hawkes+GBM** | `wc_inplay_ensemble.py` | ⚠️ | Shadow mode — ainda em validação |
| **Halftime Adjust** | `wc_halftime_adjust.py` | ✅ | Ajuste de λ no intervalo |

### 3.3 Modelos de Apoio (Funcionando)

| Modelo | Arquivo | Status | Descrição |
|--------|---------|--------|-----------|
| **EV/Kelly** | `ev_value.py` | ✅ | Expected Value + Kelly Criterion |
| **Bet Advice** | `wc_bet_advice.py` | ✅ | Cash-out + aportes + meio-mercado |
| **Bet Strategy** | `wc_bet_strategy.py` | ✅ | Posture, shields, watch list, rules |
| **Bet Guardrails** | `bet_guardrails.py` | ✅ | Bloqueio de apostas inválidas |
| **Combo Optimizer** | `wc_combo_optimizer.py` | ✅ | Otimização de bilhetes combinados |
| **Hedge Advisor** | `wc_hedge_advisor.py` | ✅ | Análise de hedge para apostas abertas |
| **Trend Advisor** | `wc_trend_advisor.py` | ✅ | Detecção de tendências no jogo |
| **Viable 2H Markets** | `wc_viable_2h_markets.py` | ✅ | Mercados disponíveis no 2º tempo |

### 3.4 Modelos LEGADOS / NÃO USADOS

| Modelo | Arquivo | Status | Problema |
|--------|---------|--------|----------|
| **Baseline** | `baseline.py` | ⚠️ Legado | Heurística simples, substituído por ensemble |
| **Bolao Predictor (LM)** | `bolao_predictor.py` | ❌ Quebrado | Fine-tuned Qwen2.5 — checkpoint não existe |
| **Hawkes Process** | `wc_hawkes.py` | ⚠️ Experimental | Shadow mode, não usado em produção |
| **GBM In-Play** | `wc_inplay_gbm.py` | ⚠️ Experimental | Shadow mode, não usado em produção |
| **Economics (CES)** | `economics.py` | ❌ Não usado | Dixit-Stiglitz — nunca integrado |
| **Math Utils** | `math_utils.py` | ✅ Usado | Funções auxiliares |

---

## 4. API Endpoints — Organização

### 4.1 Endpoints Pré-Jogo

```
POST /worldcup/predict          → Predição completa (1X2, over/under, BTTS, handicap)
POST /worldcup/simulate         → Simulação com escalações, rankings, stats
GET  /worldcup/pregame/today    → Jogos do dia com predições
GET  /worldcup/pregame/analysis → Análise detalhada (picks, escalações, fatores)
GET  /worldcup/pregame/research → Deep Research (Gemini/Moonshot/local fallback)
GET  /worldcup/schedule         → Agenda completa WC 2026
GET  /worldcup/teams            → Lista de seleções
GET  /worldcup/squads/{team}    → Escalação da seleção
GET  /worldcup/group-standings  → Classificação dos grupos
GET  /worldcup/friendlies       → Amistosos (Sofascore + FIFA)
GET  /worldcup/editions         → Histórico de edições WC
```

### 4.2 Endpoints Ao Vivo

```
GET  /worldcup/superbet/live                    → Lista eventos ao vivo
GET  /worldcup/superbet/live/{id}/advice        → In-play advice completo (modelo + strategy)
GET  /worldcup/superbet/live/{id}/optimized-tickets → Bilhetes otimizados
GET  /worldcup/superbet/live/best-picks         → Melhores picks ao vivo
GET  /worldcup/superbet/events/{id}             → Snapshot bruto Superbet
POST /worldcup/superbet/validate-builder        → Valida pernas do Criar Aposta
POST /worldcup/superbet/multiple/calculate      → Calcula Super Múltipla (+5%)
GET  /worldcup/handicap/{id}                    → Análise handicap asiático
POST /worldcup/inplay                           → Predição in-play direta (sem Superbet)
POST /worldcup/corners/predict                  → Predição de escanteios
GET  /worldcup/combo-ticket                     → Bilhete combo KXL
```

### 4.3 Endpoints de Usuário

```
POST /user/open-bets                    → Cadastra aposta aberta
GET  /user/open-bets                    → Lista apostas abertas
POST /user/open-bets/refresh-cashouts   → Atualiza cashouts
POST /user/bets/check-against-model     → Alerta se aposta vai contra modelo
POST /user/bets/simulate                → Simula resultado de apostas
GET  /user/bet-performance              → Performance histórica
POST /user/transactions/upload          → Upload extrato Superbet
GET  /user/transactions/summary         → Resumo financeiro
POST /user/transactions/reconcile       → Reconciliação automática
```

### 4.4 Endpoints de Infraestrutura

```
GET  /health/live          → Health check
GET  /health               → Health detalhado
GET  /data/pulse          → Metadados do lake
GET  /config/sportradar   → Configuração SportRadar
GET  /sportradar/lmt/{id} → Widget SportRadar
POST /news/sync           → Coleta RSS
GET  /news/feed           → Feed de notícias
GET  /news/all            → Todas as notícias
GET  /news/cards          → Cards de notícias
```

---

## 5. Frontend — Páginas e Componentes

### 5.1 Páginas Principais

| Página | Rota | Propósito | Status |
|--------|------|-----------|--------|
| **Home** | `/` | Dashboard com jogos do dia | ✅ |
| **Pre-Game Analysis** | `/analise/:home/:away` | Análise pré-jogo completa | ✅ |
| **Live In-Play** | `/ao-vivo/:eventId` | Painel ao vivo com advice | ✅ |
| **Friendlies** | `/amistosos` | Amistosos internacionais | ✅ |
| **Schedule** | `/agenda` | Agenda WC 2026 | ✅ |
| **Standings** | `/classificacao` | Classificação dos grupos | ✅ |
| **Squads** | `/escalacoes` | Escalações das seleções | ✅ |
| **User Bets** | `/apostas` | Gestão de apostas do usuário | ✅ |
| **Wallet** | `/carteira` | Extrato e reconciliação | ✅ |
| **Settings** | `/config` | Configurações | ✅ |

### 5.2 Componentes Ao Vivo (LiveInPlayPage)

```
LiveInPlayPage
├── Hero: Placar + Minuto + Odds
├── Alertas: Hedge, Against Model, P0 Guard
├── Coluna Mercados | Coluna Modelo
│   ├── LiveMarketCards (1X2, Over/Under, BTTS, Next Goal)
│   ├── LiveRefereePanel (cartões, faltas, pênaltis) ← NOVO
│   └── LiveModelPanel (probabilidades, gráficos)
├── LivePredictionEvolutionChart (histórico de probs)
├── LiveScoreHeatmap (heatmap de placares)
├── LivePlainGuide (guia rápido colapsável)
├── LiveTimelinePanel (timeline de eventos)
├── LiveFormH2hPanel (forma + H2H)
├── LivePlayerStatsPanel (stats individuais)
├── LiveSocialRadarPanel (social picks)
├── LiveStatsCompactBar (xG, posse, chutes)
├── LiveOpenBetMonitor (monitor de apostas abertas)
├── BetStrategyPanel (estratégia de apostas)
├── LiveBestCombosPanel (melhores combos)
├── LiveHalfTicketsPanel (bilhetes por período)
├── LiveRemaining2hMarketsPanel (mercados 2º tempo)
├── LiveLongshotCombosPanel (combos longshot)
├── LiveTopReturnPanel (maiores retornos)
├── LiveOptimizedTicketsPanel (bilhetes otimizados)
├── LiveActionNowPanel (ação imediata)
├── LiveModelVsMarketHero (modelo vs mercado)
├── LiveEvRealPanel (EV real-time)
├── LiveCornersPanel (escanteios)
├── LiveBetBuilderGuardPanel (validação de combos)
├── LiveRecalibrationBanner (recalibração)
├── LiveContextUpload (upload de contexto manual)
└── CashoutAlertSetup (alertas de cash-out)
```

---

## 6. Problemas Identificados

### 6.1 APIs Externas (CRÍTICO)

| Serviço | Status | Impacto | Solução |
|---------|--------|---------|---------|
| **Gemini** | ❌ Quota esgotada (429) | Deep Research sem IA | Fallback local ✅ implementado |
| **Moonshot** | ❌ Conta suspensa (429) | Deep Research sem IA | Fallback local ✅ implementado |
| **Perplexity** | ⚠️ Chave pode ser inválida | Pesquisa web fraca | Usar cache + local |
| **Superbet** | ⚠️ Intermitente | Dados ao vivo instáveis | Stale fallback ✅ implementado |
| **ScoreAlarm** | ⚠️ Timeout ocasional | Timeline/stats atrasadas | Cache + fallback |

### 6.2 Código Duplicado / Conflitos

| Problema | Localização | Severidade | Solução |
|----------|-------------|------------|---------|
| **H2H em 3 formatos** | `match_context` (h2h dict), `scorealarm.h2h`, `model_data.h2h_summary` | Média | Unificar em schema único |
| **Referee em 2 formatos** | `match_context.referee`, `match_context.referee_card_lambda` | Baixa | Usar `parse_referee_from_match_context()` |
| **Escalações em 3 fontes** | FIFA, Sofascore FEPT, match_context manual | Média | Prioridade: FIFA → FEPT → manual |
| **λ (lambda) calculado 3x** | `goal_model_factors`, `simulate_inplay`, `inplay_from_predictor` | Baixa | Cachear no predictor |

### 6.3 Módulos Não Usados / Legados

| Módulo | Linhas | Status | Ação |
|--------|--------|--------|------|
| `bolao_predictor.py` | ~200 | ❌ Quebrado | Remover ou consertar LM |
| `economics.py` | ~150 | ❌ Não usado | Remover |
| `wc_hawkes.py` | ~300 | ⚠️ Shadow | Manter em modo shadow |
| `wc_inplay_gbm.py` | ~200 | ⚠️ Shadow | Manter em modo shadow |
| `baseline.py` | ~150 | ⚠️ Legado | Deprecar, usar ensemble |
| `train.py` | ~100 | ⚠️ Legado | Consolidar em `train_cli.py` |

### 6.4 Testes

| Suite | Quantidade | Status | Problema |
|-------|------------|--------|----------|
| `test_wc_inplay_*.py` | ~100 | ✅ Passando | Boa cobertura |
| `test_wc_referee_inplay.py` | 24 | ✅ Passando | Novo |
| `test_wc_local_synthesis.py` | 16 | ✅ Passando | Novo |
| `test_wc_inplay_h2h_adjust.py` | 22 | ✅ Passando | Novo |
| `test_inplay_postmortem.py` | 1 | ❌ Falhando | Sem ticks no Parquet |
| `test_inplay_ensemble_readiness.py` | 1 | ✅ Fixado | Mock incompleto |
| **Total** | **~850** | **~98% passando** | |

### 6.5 Frontend

| Problema | Status | Solução |
|----------|--------|---------|
| **Build lento** (2.8MB JS) | ⚠️ | Code-splitting com dynamic imports |
| **Chunk >500KB** | ⚠️ | Configurar manualChunks no Vite |
| **TypeScript strict** | ✅ | 0 erros |
| **Componentes não usados** | ⚠️ | Audit e remover |

---

## 7. O Que Funciona vs. O Que Não Funciona

### ✅ FUNCIONANDO BEM

1. **Predição pré-jogo WC**: Ensemble completo (Poisson + Dixon-Coles + Logistic + KXL) → acurácia ~65-70%
2. **Simulação de amistosos**: FIFA + Sofascore + ensemble → funciona para jogos fora da tabela
3. **In-play básico**: Poisson MC + Bayesian update → probabilidades condicionadas ao placar
4. **Mercados de escanteios**: Modelo próprio com xG proxy → funciona bem
5. **Handicap asiático**: Monte Carlo + EV/Kelly → funciona bem
6. **Bet strategy**: Posture, shields, watch list → funciona bem
7. **Cash-out advisor**: EV remaining + trend → funciona bem
8. **Bet guardrails**: Bloqueio de apostas inválidas → funciona bem
9. **Combo optimizer**: Otimização de bilhetes → funciona bem
10. **User bets tracking**: Cadastro, monitor, cash-out → funciona bem
11. **Wallet reconciliation**: Upload extrato + reconciliação → funciona bem
12. **Fallback local**: Quando APIs externas falham → funciona bem

### ⚠️ FUNCIONANDO COM LIMITAÇÕES

1. **Deep Research**: Só funciona com fallback local (Gemini/Moonshot fora)
2. **Ensemble in-play (Hawkes+GBM)**: Shadow mode — não usado em produção
3. **Superbet live data**: Intermitente — stale fallback ativo
4. **Sofascore live stats**: Nem sempre disponível antes do apito
5. **LM (Qwen2.5)**: Checkpoint não existe — fallback para baseline

### ❌ NÃO FUNCIONANDO

1. **Gemini API**: Quota esgotada (429) — precisa de nova chave ou plano pago
2. **Moonshot API**: Conta suspensa — precisa recarregar saldo
3. **Perplexity**: Pode estar com chave inválida
4. **Postmortem automático**: Teste falhando — sem ticks no Parquet para evento de teste

---

## 8. Linha de Raciocínio Reorganizada

### 8.1 Fluxo Pré-Jogo (Funcionando)

```
Usuário escolhe jogo (ex: Brasil x Haiti)
         │
         ▼
┌─────────────────────┐
│ 1. Dados Históricos │ ← WC fixtures (1930-2022) + rankings FIFA
│ 2. Stats Sofascore  │ ← xG, chutes, posse (últimos jogos)
│ 3. KXL Baselines    │ ← DNA tático por seleção
│ 4. Elo Iterativo    │ ← Calculado a partir de resultados
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Feature Engineering │
│ - 40+ features      │
│ - H2H, forma, xG   │
│ - Elo, rankings    │
│ - Lesões, escalações │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Modelos Pré-Jogo    │
│ - Poisson           │ → λ home, λ away
│ - Dixon-Coles       │ → ρ (correlação empate)
│ - Logistic          │ → prob 1/X/2
│ - KXL Collision     │ → vetores táticos
│ - Draw Model        │ → prob empate específica
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Ensemble Blend      │
│ - Peso otimizado    │
│ - Brier score       │
│ - KXL blend 20%     │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Output Pré-Jogo     │
│ - 1/X/2 probs       │
│ - Over/Under probs  │
│ - BTTS prob         │
│ - Handicap lines    │
│ - Scorelines        │
│ - Picks + Kelly     │
│ - Bet strategy      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Deep Research       │ ← Gemini/Moonshot (OFF) → Fallback local
│ - Resumo executivo  │
│ - Fatores + Riscos  │
│ - Escalações        │
│ - Árbitro           │
│ - Picks recomendados│
└─────────────────────┘
```

### 8.2 Fluxo Ao Vivo (Funcionando)

```
Evento Superbet ao vivo (ex: Brasil 0x1 Haiti, 30')
         │
         ▼
┌─────────────────────┐
│ 1. Snapshot Superbet│ ← Odds atuais, placar, minuto
│ 2. ScoreAlarm       │ ← Timeline, stats, forma
│ 3. Sofascore        │ ← xG, posse, chutes (se disponível)
│ 4. Match Context    │ ← Contexto manual (referee, xG, H2H)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Modelo In-Play      │
│ - λ pré-jogo        │ ← Do predictor
│ - Bayesian update   │ ← Ajusta com gols observados
│ - H2H adjust        │ ← Comeback boost se domina H2H
│ - Live stats adjust │ ← xG, posse, chutes
│ - Momentum          │ ← Gols, cartões, corners
│ - Market shrinkage  │ ← Mistura com odds do mercado
│ - NHPP              │ ← Intensidade por período
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Simulação MC        │
│ - 10.000 simulações │
│ - Condicionada ao  │
│   placar atual      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Output Ao Vivo      │
│ - Prob 1/X/2 FT     │
│ - Prob 1/X/2 2T     │
│ - Next goal         │
│ - Over/Under        │
│ - BTTS              │
│ - Handicap          │
│ - Corners           │
│ - Cards (referee)   │ ← NOVO
│ - Cash-out advice   │
│ - Aportes           │
│ - Strategy          │
└─────────────────────┘
```

---

## 9. Recomendações de Organização

### 9.1 Curto Prazo (esta semana)

1. **Consertar APIs externas**
   - [ ] Nova chave Gemini ou migrar para outro modelo
   - [ ] Recarregar saldo Moonshot ou desativar
   - [ ] Verificar chave Perplexity

2. **Unificar H2H**
   - [ ] Criar schema único para H2H (usar formato do `wc_inplay_h2h_adjust`)
   - [ ] Remover formatos legados

3. **Documentar fallback local**
   - [ ] O fallback local está funcionando bem — documentar como feature

### 9.2 Médio Prazo (este mês)

1. **Remover código morto**
   - [ ] `bolao_predictor.py` (LM quebrado)
   - [ ] `economics.py` (não usado)
   - [ ] `baseline.py` (legado)

2. **Code-splitting frontend**
   - [ ] Dynamic imports para páginas pesadas
   - [ ] Reduzir bundle size

3. **Melhorar testes**
   - [ ] Fixar `test_inplay_postmortem.py`
   - [ ] Adicionar testes de integração para endpoints principais

### 9.3 Longo Prazo (próximos meses)

1. **Revisar ensemble in-play**
   - [ ] Validar Hawkes + GBM com dados reais
   - [ ] Decidir se vale a pena manter

2. **Migrar para modelo de linguagem local**
   - [ ] Substituir Gemini/Moonshot por modelo local (Ollama/Llama)
   - [ ] Eliminar dependência de APIs externas

3. **Automatizar coleta de dados**
   - [ ] Pipeline de coleta automática de stats pré-jogo
   - [ ] Integração com mais fontes (WhoScored, FBref)

---

## 10. Conclusão

**O projeto está funcionando bem para o core (predição pré-jogo + ao vivo).**

Os principais problemas são:
1. **APIs externas fora** → Já tem fallback local ✅
2. **Código duplicado** → Precisa de refatoração
3. **Código morto** → Precisa de limpeza

**A arquitetura está correta**: medalhão de dados + modelos especializados + ensemble + API REST + frontend React.

**O que precisa de atenção imediata**:
- Resolver APIs externas (ou aceitar fallback local como padrão)
- Limpar código morto
- Documentar melhor o fluxo de dados
