# Documentação — Bolão AI / api_noticia

Plataforma de previsões esportivas (bolão 1/X/2) que combina **datalake de notícias**, **modelos estatísticos**, **motor tático KXL** e **interface web moderna**.

## Índice

| Documento | Conteúdo |
|-----------|----------|
| [Visão geral](visao-geral.md) | Objetivo, escopo, formato bolão, fluxo end-to-end |
| [Arquitetura](arquitetura.md) | Camadas, diagramas, estrutura de pastas |
| [Instalação e configuração](instalacao-e-configuracao.md) | Setup, `.env`, scripts, dois terminais dev |
| [Referência da API](api-referencia.md) | Todos os endpoints REST com exemplos |
| [Modelos preditivos](modelos-preditivos.md) | Dixon-Coles, logística, Elo, KXL, ensemble, EV |
| [Datalake e pipelines](datalake-e-pipelines.md) | Bronze/silver/gold, CLIs, importação de fixtures |
| [Frontend](frontend.md) | React, rotas, Clean Architecture, componentes |
| [Motor KXL — Colisão](kxl-colisao.md) | Fórmulas Vcar, Vesc, TBRTL, letalidade×GK |
| [Glossário](glossario.md) | Termos técnicos e siglas |

## Início rápido

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
import-world-cup --missing-only
./scripts/dev-api.sh

# Frontend (outro terminal)
cd frontend && npm install && npm run dev
```

- API: http://localhost:8000/docs  
- UI: http://localhost:5173  

## Repositório

```
api_noticia/
├── api/              # FastAPI
├── ingest/           # RSS, fixtures, odds
├── pipelines/        # Silver, gold, WC, KXL
├── models/           # ML e previsão
├── schemas/          # Contratos Pydantic
├── frontend/         # React + TypeScript
├── data/             # Rodadas, baselines KXL, sources.yaml
├── docs/             # Esta documentação
└── tests/
```

## Licença e uso

Uso interno / pesquisa. Respeite os termos dos portais de notícias e das APIs externas (The Odds API).
