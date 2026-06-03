# Visão geral

## O que é o projeto

O **api_noticia** (marca UI: **Bolão AI**) é uma plataforma para:

1. **Coletar** notícias esportivas de portais brasileiros (RSS)
2. **Transformar** dados em camadas analíticas (datalake bronze → silver → gold)
3. **Prever** resultados de bolão (**1** = vitória mandante, **X** = empate, **2** = vitória visitante)
4. **Validar** modelos em jogos históricos da Copa do Mundo
5. **Cruzar** probabilidades com odds reais (expected value)
6. **Exibir** tudo em dashboard web com gráficos e contexto IA

## Público-alvo

- Analistas e entusiastas de bolão
- Desenvolvedores que estendem pipelines de dados esportivos
- Pesquisa em modelos híbridos (estatística + contexto tático KXL + notícias)

## Formato bolão

| Código | Significado |
|--------|-------------|
| `1` | Vitória do mandante |
| `X` | Empate |
| `2` | Vitória do visitante |

## Fluxo principal (Copa do Mundo)

```mermaid
flowchart TB
    subgraph dados [Dados]
        WC[Fixtures WC 1930-2022]
        KXL[Baselines KXL 48 seleções]
        ODDS[The Odds API]
    end

    subgraph modelos [Modelos]
        DC[Dixon-Coles]
        LOG[Regressão logística]
        ENS[Ensemble calibrado]
        DNA[Blend KXL 25%]
        COL[Colisão setorial]
    end

    subgraph saida [Saída]
        API[FastAPI]
        UI[Frontend React]
    end

    WC --> DC
    WC --> LOG
    DC --> ENS
    LOG --> ENS
    ENS --> DNA
    KXL --> DNA
    KXL --> COL
    COL --> DNA
    DNA --> API
    ODDS --> API
    API --> UI
```

## Fluxo principal (Brasileirão)

```mermaid
flowchart LR
    RSS[RSS portais] --> Bronze
    Bronze --> Silver
    Silver --> Gold
    Gold --> Baseline[Heurística baseline]
    Fixtures[Brasileirão fixtures] --> Gold
    Baseline --> API
```

## Capacidades por módulo

| Módulo | Função |
|--------|--------|
| **Ingestão** | RSS, import Brasileirão/Copa, odds ao vivo |
| **Pipelines** | Silver/gold, palpites rodada, validação histórica |
| **Modelos** | Dixon-Coles, logística, Elo, KXL, EV |
| **API** | REST JSON, CORS, warmup de modelos na subida |
| **Frontend** | Dashboard, palpite, validação, notícias, value bets |

## Roadmap (README principal)

- Fine-tuning de LM com JSONL gold
- NER de jogadores
- BigQuery/GCS para escala
- Orquestração (Prefect / Composer)
