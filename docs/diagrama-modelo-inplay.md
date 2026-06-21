# Diagrama: Como o Modelo Gera Palpites Ao Vivo (In-Play)

> Este diagrama mostra o fluxo completo desde a coleta de dados da Superbet até o palpite final exibido no frontend.

---

## 1. Diagrama de Arquitetura (Visão Geral)

```mermaid
flowchart TB
    subgraph COLETA["1. COLETA DE DADOS AO VIVO"]
        SB["Superbet API<br/>(httpx + SSE)"]
        SB_CACHE["Cache Bronze<br/>data/lake/bronze/superbet/events/{id}/latest.json"]
        SB_PARSER["Parser Superbet<br/>SuperbetEventSnapshot"]
    end

    subgraph ENRIQUECIMENTO["2. ENRIQUECIMENTO (Opcional)"]
        SOFA["Sofascore Live<br/>momentum + stats (xG, posse)"]
        SCORE["ScoreAlarm<br/>timeline + h2h"]
        HT["Halftime Stats<br/>ajuste λ para 2º tempo"]
    end

    subgraph PRE_JOGO["3. MODELO PRÉ-JOGO (Base)"]
        FIX["Fixtures WC<br/>(1930-2022)"]
        FEAT["Feature Engineering<br/>Elo, H2H, forma, xG, FIFA rankings"]
        COLLAB["Ensemble Colaborativo<br/>Dixon-Coles + Regressão Logística<br/>otimizado por Brier score"]
        KXL["Motor Tático KXL<br/>Energy × Space × Time<br/>Vcar × Vesc colisão setorial"]
        DRAW["Draw Model<br/>modelo dedicado para empate"]
        PRE_BLEND["Blend Final<br/>ensemble + KXL + draw floor"]
        LAMBDA["λ pré-jogo<br/>força de ataque/defesa"]
    end

    subgraph INPLAY["4. MODELO IN-PLAY (Ao Vivo)"]
        BAYES["Bayesian Update<br/>ajusta λ com gols observados"]
        LIVE_ADJ["Live Stats Adjust<br/>posse, xG, chutes"]
        MARKET_SHR["Market Shrinkage<br/>mistura com implícito mercado"]
        NHPP["NHPP<br/>λ por período (1T/2T)"]
        MOMENTUM["Momentum<br/>fator de intensidade"]
        HT_ADJ["Halftime Adjust<br/>stats intervalo"]
        TRAIL["Trailing Chase<br/>boost se time busca resultado"]
        MC["Monte Carlo<br/>n=2000+ amostras Poisson bivariada"]
        INPLAY_BLEND["Ensemble In-Play<br/>Hawkes + GBM + Market"]
        RESULT["InPlayResult<br/>40+ probabilidades"]
    end

    subgraph ADVICE["5. CONSELHOS DE APOSTAS"]
        CONF["Confidence Score<br/>padrões históricos"]
        CASHOUT["Cash-out Advisor<br/>compara prob vs odd entrada"]
        APORTES["Aporte Advisor<br/>scan_all_market_edges()<br/>EV + Kelly + edge_pp"]
    end

    subgraph STRATEGY["6. ESTRATÉGIA"]
        POSTURE["Posture<br/>atacar / neutro / defensivo"]
        SHIELDS["Shields<br/>armadilhas da casa, handicap agressivo"]
        OPPS["Opportunities<br/>forte / moderada / leve"]
        COMBO["Combo Ticket KXL"]
        SUPER["Super Múltipla +5%"]
    end

    subgraph API["7. API FASTAPI"]
        ENDPOINT["GET /worldcup/superbet/live/{id}/advice<br/>WcSuperbetLiveAdviceResponse"]
    end

    subgraph FRONTEND["8. FRONTEND REACT"]
        HERO["LiveActionNowPanel<br/>'O que fazer agora'"]
        MARKET_CARDS["LiveMarketCards<br/>🟢 APOSTAR / 🟡 QUASE / ⚪ SEM VALOR"]
        MODEL_PANEL["LiveModelPanel<br/>barras de probabilidade %"]
        STRATEGY_PANEL["BetStrategyPanel<br/>posture + shields + oportunidades"]
        CASHOUT_PANEL["LiveOpenBetMonitor<br/>cash-out / EV residual"]
        GUIDE["LivePlainGuide<br/>guia colapsável em português"]
    end

    SB --> SB_CACHE
    SB_CACHE --> SB_PARSER
    SB_PARSER --> SOFA
    SB_PARSER --> SCORE
    SOFA --> BAYES
    SCORE --> BAYES
    HT --> HT_ADJ

    FIX --> FEAT
    FEAT --> COLLAB
    FEAT --> KXL
    COLLAB --> PRE_BLEND
    KXL --> PRE_BLEND
    DRAW --> PRE_BLEND
    PRE_BLEND --> LAMBDA

    LAMBDA --> BAYES
    BAYES --> LIVE_ADJ
    LIVE_ADJ --> MARKET_SHR
    MARKET_SHR --> NHPP
    NHPP --> MOMENTUM
    MOMENTUM --> HT_ADJ
    HT_ADJ --> TRAIL
    TRAIL --> MC
    MC --> INPLAY_BLEND
    INPLAY_BLEND --> RESULT

    RESULT --> CONF
    CONF --> CASHOUT
    CONF --> APORTES

    CASHOUT --> POSTURE
    APORTES --> POSTURE
    APORTES --> OPPS
    POSTURE --> SHIELDS
    OPPS --> COMBO
    OPPS --> SUPER

    POSTURE --> ENDPOINT
    SHIELDS --> ENDPOINT
    OPPS --> ENDPOINT
    COMBO --> ENDPOINT
    SUPER --> ENDPOINT
    CASHOUT --> ENDPOINT
    RESULT --> ENDPOINT

    ENDPOINT --> HERO
    ENDPOINT --> MARKET_CARDS
    ENDPOINT --> MODEL_PANEL
    ENDPOINT --> STRATEGY_PANEL
    ENDPOINT --> CASHOUT_PANEL
    ENDPOINT --> GUIDE
```

---

## 2. Diagrama de Sequência (Fluxo Temporal)

```mermaid
sequenceDiagram
    autonumber
    participant User as Usuário
    participant FE as Frontend React<br/>(LiveInPlayPage)
    participant API as API FastAPI
    participant SB as SuperbetClient<br/>(httpx)
    participant Parser as SuperbetParser
    participant Sofa as Sofascore Live
    participant Predictor as WcPredictor<br/>(pré-jogo)
    participant InPlay as wc_inplay.py<br/>(modelo ao vivo)
    participant Advice as wc_bet_advice.py
    participant Strategy as wc_bet_strategy.py
    participant Tick as LiveTicks<br/>(Parquet)

    Note over User,Tick: Polling Adaptativo (~10s fast / ~60s full)

    loop A cada ciclo de polling
        FE->>API: GET /superbet/live/{id}/advice?fast=true
        API->>SB: fetch_event(event_id)
        SB-->>API: JSON raw Superbet
        API->>Parser: parse_superbet_event()
        Parser-->>API: SuperbetEventSnapshot

        alt Não fast mode
            API->>Sofa: enrich_momentum_from_sofascore()
            Sofa-->>API: live stats, xG, posse
        end

        API->>Predictor: predict(home, away, phase)
        Predictor-->>API: λ_home, λ_away (pré-jogo)

        API->>InPlay: simulate_inplay(λ, score, minute, ...)
        Note right of InPlay: Bayesian update<br/>Live adjust<br/>Monte Carlo<br/>Ensemble blend
        InPlay-->>API: InPlayResult (40+ probs)

        API->>Advice: build_bet_advice_report()
        Note right of Advice: EV, Kelly, cash-out<br/>scan_all_market_edges()
        Advice-->>API: CashoutAdvice + AporteAdvice[]

        API->>Strategy: build_bet_strategy_report()
        Note right of Strategy: Posture, shields<br/>combo ticket, super múltipla
        Strategy-->>API: StrategyReport

        API->>Tick: append_live_tick()
        Tick-->>API: OK (Parquet bronze)

        API-->>FE: WcSuperbetLiveAdviceResponse (JSON)

        FE->>FE: mergeLiveAdvice(fast, full)
        FE->>User: Renderiza:
        Note over FE,User: • Hero: "O que fazer agora"<br/>• MarketCards: vereditos APOSTAR/QUASE/SEM VALOR<br/>• ModelPanel: barras de prob %<br/>• StrategyPanel: posture + shields<br/>• OpenBetMonitor: cash-out
    end

    alt Detecta gol (reactive boost)
        FE->>FE: applyReactivePollBoost()
        Note over FE: Polling acelera para ~2s por 30s
    end
```

---

## 3. Diagrama de Componentes do Modelo In-Play

```mermaid
flowchart LR
    subgraph INPUT["Entradas"]
        I1["Placar (home_score, away_score)"]
        I2["Minuto de jogo"]
        I3["λ pré-jogo (ensemble)"]
        I4["Eventos ao vivo (gols, cartões)"]
        I5["Live stats (posse, xG, chutes)"]
        I6["Odds mercado (implícito)"]
        I7["Stats intervalo (se HT)"]
    end

    subgraph PROCESSAMENTO["Processamento Interno"]
        P1["Bayesian Lambda Update<br/>Gamma-Poisson conjugada"]
        P2["Live Stats Adjust<br/>fator de intensidade"]
        P3["Market Shrinkage<br/>James-Stein / implícito"]
        P4["NHPP Half-Lambdas<br/>intensidade não-homogênea"]
        P5["Momentum Computation<br/>trailing chase boost"]
        P6["Halftime Adjust<br/>re-calibração 2T"]
        P7["Poisson Bivariada MC<br/>n=2000 amostras com ρ"]
        P8["Ensemble In-Play<br/>Hawkes + GBM + Market"]
    end

    subgraph OUTPUT["Saídas (InPlayResult)"]
        O1["1X2 FT / 1T / 2T"]
        O2["Over/Under 1.5, 2.5, 3.5, 4.5"]
        O3["BTTS, Next Goal, No More Goals"]
        O4["Handicap Europeu e Asiático"]
        O5["Correct Scores, Exact Totals"]
        O6["Combo Markets"]
        O7["Top HT/FT Duplas"]
        O8["Ensemble Shadow<br/>(Poisson vs ensemble)"]
    end

    I1 --> P1
    I2 --> P4
    I3 --> P1
    I4 --> P2
    I5 --> P2
    I6 --> P3
    I7 --> P6
    I4 --> P5

    P1 --> P4
    P2 --> P4
    P3 --> P4
    P4 --> P7
    P5 --> P7
    P6 --> P7
    P7 --> P8
    P8 --> O1
    P8 --> O2
    P8 --> O3
    P8 --> O4
    P8 --> O5
    P8 --> O6
    P8 --> O7
    P8 --> O8
```

---

## 4. Diagrama de Decisão: Como o Palpite é Gerado

```mermaid
flowchart TD
    START(["Usuário acessa<br/>/ao-vivo/:eventId"]) --> POLL["Frontend inicia polling<br/>adaptativo (10s/60s)"]
    POLL --> API_CALL["API chama<br/>run_live_advice()"]

    API_CALL --> FETCH["fetch_event_with_stale_fallback()<br/>Superbet API → JSON"]
    FETCH --> PARSE["parse_superbet_event()<br/>→ SuperbetEventSnapshot"]

    PARSE --> CHECK_FAST{"fast=true?"}
    CHECK_FAST -->|Sim| SKIP_SOFA["Pula Sofascore<br/>usa dados cache"]
    CHECK_FAST -->|Não| ENRICH["enrich_momentum_from_sofascore()<br/>fetch_scorealarm_context()"]

    SKIP_SOFA --> PRE_JOGO["WcPredictor.predict()<br/>→ λ pré-jogo"]
    ENRICH --> PRE_JOGO

    PRE_JOGO --> INPLAY["simulate_inplay()<br/>Monte Carlo Poisson bivariada"]
    INPLAY --> RESULT["InPlayResult<br/>40+ probabilidades"]

    RESULT --> ADVICE["build_bet_advice_report()"]
    ADVICE --> CHECK_BET{"Usuário tem<br/>aposta aberta?"}

    CHECK_BET -->|Sim| CASHOUT["advise_cashout()<br/>manter/aguardar/cashout_parcial/cashout"]
    CHECK_BET -->|Não| SKIP_CASHOUT["Pula cash-out"]

    CASHOUT --> APORTES["advise_aportes()<br/>scan_all_market_edges()<br/>EV + Kelly + edge_pp"]
    SKIP_CASHOUT --> APORTES

    APORTES --> STRATEGY["build_bet_strategy_report()<br/>posture, shields, opportunities"]
    STRATEGY --> PAYLOAD["Monta payload JSON<br/>inplay_summary + cashout + aportes + strategy + ..."]

    PAYLOAD --> TICK["append_live_tick()<br/>grava Parquet bronze"]
    TICK --> RESPONSE["Retorna<br/>WcSuperbetLiveAdviceResponse"]

    RESPONSE --> FE_RENDER["Frontend renderiza:<br/>• Hero CTA<br/>• MarketCards (APOSTAR/QUASE/SEM VALOR)<br/>• ModelPanel (barras %)<br/>• StrategyPanel (posture + shields)<br/>• OpenBetMonitor (cash-out)"]

    FE_RENDER --> USER_SEES(["Usuário vê<br/>palpite ao vivo"])

    style START fill:#e1f5fe
    style USER_SEES fill:#c8e6c9
    style INPLAY fill:#fff3e0
    style APORTES fill:#fff3e0
    style STRATEGY fill:#fff3e0
```

---

## 5. Resumo dos Módulos Principais

| Módulo | Arquivo | Função |
|--------|---------|--------|
| **Coleta** | `ingest/superbet/client.py` | HTTP Superbet (httpx + SSE) |
| **Cache** | `ingest/superbet/store.py` | Fallback bronze JSON + stale |
| **Parser** | `ingest/superbet/parser.py` | Converte raw → SuperbetEventSnapshot |
| **Predictor Pré-Jogo** | `models/wc_predictor.py` | Ensemble + KXL + draw model |
| **Modelo In-Play** | `models/wc_inplay.py` | Poisson MC + Bayesian + momentum |
| **Handicap** | `models/wc_handicap.py` | Probabilidades handicap asiático |
| **Conselhos** | `models/wc_bet_advice.py` | Cash-out + aportes (EV/Kelly) |
| **Estratégia** | `models/wc_bet_strategy.py` | Posture, shields, combo ticket |
| **Orquestração** | `ingest/superbet/advice.py` | Junta tudo em run_live_advice() |
| **API** | `api/main.py` | Endpoints /worldcup/superbet/live/* |
| **Frontend** | `frontend/src/presentation/pages/LiveInPlayPage.tsx` | Página ao vivo com 4 tabs |

---

## 6. Exemplo de Payload de Resposta

```json
{
  "event_id": "13127506",
  "inplay_summary": {
    "prob_final_home": 0.42,
    "prob_final_draw": 0.28,
    "prob_final_away": 0.30,
    "over_25": 0.55,
    "btts": 0.48,
    "prob_next_goal_home": 0.45,
    "prob_no_more_goals": 0.12,
    "lambda_adjustment": "prior → full"
  },
  "cashout": {
    "action": "manter",
    "confidence": 0.72,
    "reason": "EV residual positivo, modelo favorece mesmo resultado"
  },
  "aportes": [
    {
      "market": "h2h",
      "outcome": "home",
      "model_prob": 0.42,
      "market_odd": 2.80,
      "ev": 0.176,
      "edge_pp": 5.2,
      "kelly_fraction": 0.063,
      "stake_suggested": 31.50,
      "classification": "forte"
    }
  ],
  "strategy": {
    "posture": "atacar_com_limite",
    "shields": ["evitar_handicap_agressivo_2t"],
    "opportunities": [
      {"tier": "forte", "market": "h2h_home", "ev": 0.176, "stake": 31.50}
    ],
    "watch_list": ["over_25", "btts_yes"]
  },
  "live_stats": {
    "possession_home": 58,
    "xg_home": 1.2,
    "xg_away": 0.8,
    "shots_home": 8,
    "shots_away": 4
  },
  "superbet_stale": false
}
```

---

## 7. Polling Adaptativo no Frontend

```mermaid
flowchart LR
    subgraph NORMAL["Modo Normal"]
        N1["Fast Query<br/>~10s"]
        N2["Full Query<br/>~60s"]
    end

    subgraph BOOST["Modo Boost (gol detectado)"]
        B1["Reactive Boost<br/>~2s por 30s"]
    end

    subgraph STALE["Modo Stale"]
        S1["Superbet indisponível<br/>usa bronze cache"]
        S2["Badge 'stale'<br/>continua polling"]
    end

    N1 --> N2
    N2 --> N1
    N1 -->|Gol detectado| B1
    B1 -->|30s expira| N1
    N1 -->|API falha| S1
    S1 --> S2
    S2 -->|API volta| N1
```
