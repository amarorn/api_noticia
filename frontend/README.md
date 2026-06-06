# Bolão AI — Frontend

Plataforma web de previsões esportivas com IA, consumindo a API FastAPI do projeto.

## Stack

- React 18 + TypeScript + Vite
- Tailwind CSS (tema dark neon / glassmorphism)
- ApexCharts, Framer Motion, TanStack Query
- Clean Architecture (domain → application → infrastructure → presentation)

## Pré-requisitos

- Node.js 18+
- API rodando em `http://localhost:8000`

## Rodar API + frontend (desenvolvimento)

Use **dois terminais** na raiz do repositório (`api_noticia`):

**Terminal 1 — API FastAPI (porta 8000):**

```bash
source .venv/bin/activate
./scripts/dev-api.sh
# ou: uvicorn api.main:app --reload --port 8000 --reload-exclude 'data/*'
```

Use `dev-api.sh` (reload só em `api/`) ou, para máxima estabilidade com o feed de notícias, `./scripts/dev-api-stable.sh` (sem reload).

**Terminal 2 — frontend Vite (porta 5173):**

```bash
cd frontend
npm install
npm run dev
```

Sem a API na porta 8000, o proxy Vite retorna `ECONNREFUSED` nas rotas `/api/*`.

| Erro no terminal Vite | Causa usual |
|----------------------|-------------|
| `ECONNREFUSED` | API não está rodando — suba o terminal 1 com `./scripts/dev-api.sh` |
| `ECONNRESET` em `/news/sync` | Uvicorn reiniciou no meio da coleta — use `dev-api.sh` (exclui `data/` do watch) |

Dados WC: se `/worldcup/*` falhar por fixtures vazias, importe com `import-world-cup` (ver README principal).

## Setup

```bash
cd frontend
npm install
npm run dev
```

Acesse [http://localhost:5173](http://localhost:5173).

O Vite faz proxy de `/api/*` para `http://localhost:8000` (sem prefixo `/api`).

## Variáveis de ambiente

Crie `.env` se necessário:

```env
VITE_API_URL=/api
# VITE_API_KEY=...   # só se não usar API_KEY no .env da raiz do repo
```

Com `API_KEY` no `.env` da **raiz** do projeto, `npm run dev` já envia `X-API-Key` (via `vite.config.ts`). Reinicie o Vite após alterar a chave.

Para apontar direto à API (sem proxy):

```env
VITE_API_URL=http://localhost:8000
```

## Build de produção

```bash
npm run build
npm run preview
```

## Páginas

| Rota | Descrição |
|------|-----------|
| `/` | Dashboard WC — rodada atual + value bets |
| `/news` | Feed de notícias |
| `/predict` | Palpite avulso WC (seleção de times e fase) |
| `/validate` | Validar histórico (backtest por jogo) |
| `/brasileirao` | Palpites da rodada do Brasileirão |
| `/match/:home/:away` | Análise detalhada de um jogo WC |

## Arquitetura

```
src/
├── domain/          # Entidades e interfaces de repositório
├── application/     # Use cases e DTOs
├── infrastructure/  # Client HTTP, mappers, repos concretos
└── presentation/    # Componentes, páginas, tema
```

Documentação completa: [../docs/frontend.md](../docs/frontend.md)

## API consumida

- `GET /health`
- `GET /news/feed`, `POST /news/sync`
- `GET /worldcup/round`
- `POST /worldcup/predict`
- `GET /worldcup/teams`
- `GET /worldcup/editions`, `GET /worldcup/editions/{season}/matches`
- `POST /worldcup/validate`
- `POST /worldcup/value/live` (requer `ODDS_API_KEY`)
- `GET /round/predict`
