# Deploy na Fly.io (container + volume)

A API sobe como container Docker; dados mutáveis (lake, fixtures WC, artefato do modelo, cache de rodada) ficam no volume **`/data`**.

## Pré-requisitos

- Conta em [fly.io](https://fly.io)
- CLI: `brew install flyctl` ou [instalação oficial](https://fly.io/docs/hands-on/install-flyctl/)
- `fly auth login`
- Repositório com `data/wc/` (baselines, hyperparams, squads) e `data/rounds/`

## 1. Criar app e volume (primeira vez)

Na raiz do projeto:

```bash
# Nome único global na Fly — altere em fly.toml se "api-noticia" já existir
fly apps create api-noticia

fly volume create api_noticia_data --region gru --size 3 -a api-noticia
```

Região **`gru`** (São Paulo) reduz latência para usuários no Brasil.

## 2. Segredos (opcional)

```bash
fly secrets set API_KEY="$(openssl rand -hex 32)" -a api-noticia
fly secrets set ODDS_API_KEY=sua_chave -a api-noticia
# fly secrets set API_FOOTBALL_KEY=... -a api-noticia
```

No build do frontend use a mesma chave em `VITE_API_KEY`.

Liste com `fly secrets list -a api-noticia`.

## 3. Deploy

```bash
fly deploy -a api-noticia
```

URL pública: `https://api-noticia.fly.dev` (ou o hostname que a Fly mostrar).

- Swagger: `https://<app>.fly.dev/docs`
- Liveness (proxy): `https://<app>.fly.dev/health/live`
- Health completo: `https://<app>.fly.dev/health`

## 4. Dados da Copa (obrigatório na primeira vez)

O volume começa vazio. Entre na máquina e importe fixtures históricos:

```bash
fly ssh console -a api-noticia -C "import-world-cup --missing-only"
```

Treine e persista o artefato no volume (evita ~45s de retreino a cada restart):

```bash
fly ssh console -a api-noticia -C "train-wc --force"
```

Verifique o health:

```bash
curl -s "https://api-noticia.fly.dev/health" | python3 -m json.tool
```

`wc_models_ready` deve ser `true` e `wc_artifact.loaded_from_cache` preferencialmente `true`.

## 5. Frontend

A UI continua em outro host (Vercel, Netlify, etc.). No build do frontend:

```env
VITE_API_URL=https://api-noticia.fly.dev
```

CORS da API já aceita `*`; em produção restrita você pode configurar proxy ou ajustar `api/main.py`.

## Variáveis no `fly.toml`

| Variável | Valor | Uso |
|----------|--------|-----|
| `LAKE_ROOT` | `/data/lake` | Bronze/silver/gold, cache |
| `WC_ARTIFACT_DIR` | `/data/lake/artifacts/wc_predictor` | Pickle do `WcPredictor` |
| `PORT` | `8080` | Porta interna do uvicorn |

## Operação

| Ação | Comando |
|------|---------|
| Logs | `fly logs -a api-noticia` |
| SSH | `fly ssh console -a api-noticia` |
| Escalar RAM | editar `[[vm]] memory` em `fly.toml` e `fly deploy` |
| Aumentar disco | `fly volume extend <volume_id> -s 5` |
| Coletar notícias | `fly ssh console -a api-noticia -C "collect-news"` |

## Custos e comportamento

- **`min_machines_running = 1`** e **`auto_stop_machines = "off"`**: máquina sempre ligada — melhor para o modelo não “dormir” (evita cold start longo).
- **1 GB RAM**: suficiente para sklearn + artefato; se retreinar na subida falhar, suba para `2gb` em `fly.toml`.
- Volume **~US$ 0,15/GB/mês** (ver preços atuais na Fly).

## Troubleshooting

| Sintoma | Solução |
|---------|---------|
| Proxy `[PR03]` / `[PR01] no healthy instances` | Janela curta durante `fly deploy` (app com **volume** = uma máquina; tráfego cai até o uvicorn subir). Aguarde ~30s e teste `/health/live`. Evite dois deploys seguidos. |
| `/worldcup/*` 503 | Importar fixtures + `train-wc --force` |
| Health `wc_models_ready: false` | Ver logs: `fly logs`; conferir fixtures em `/data/lake/fixtures` |
| Deploy sem volume | Criar volume na mesma região `gru` antes do deploy |
| Nome de app em uso | Alterar `app = "..."` em `fly.toml` e repetir `fly apps create` |

O health check do proxy usa `GET /health/live` (resposta imediata). O endpoint completo `GET /health` inclui contadores do lake e estado do modelo WC.

## Atualizar código

```bash
git pull
fly deploy -a api-noticia
```

O volume **preserva** lake, artefato e cache entre deploys.
