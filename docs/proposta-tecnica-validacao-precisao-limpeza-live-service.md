# Proposta Técnica — Loop de Validação, Quick Wins de Precisão, Limpeza e Fronteira do Live Service

> Data: 2026-08-04 · **Atualização implementação:** 2026-08-05 (WS1 slice diário + semanal)
> Escopo: `/Users/amaro/Documents/Cactus/api_noticia`
> Base: análises `arquitetura-analise-2026-06-21.md` e `analise-modelo-aovivo-precisao.md`, verificadas contra o código atual
> Premissa de sequência: **validar → precisar → limpar → expandir**. Nada de novo esporte/mercado até os 4 workstreams fecharem.

---

## 0. Estado verificado em 04/08 (o que mudou desde a análise de junho)

| Item do diagnóstico de junho | Estado real hoje | Consequência para esta proposta |
|---|---|---|
| xG acumulado ao vivo não entra no λ | **Parcialmente resolvido** — `wc_inplay.py:640-680` já aplica `adjust_lambdas_from_xg` (e modo agressivo via `wc_inplay_xg_aggressive`) | Workstream 2 vira **calibração e validação** do que existe, não implementação do zero |
| `inplay_use_calibrated_nhpp=false` | **Resolvido** — `config.py:169` agora é `True` | Resta garantir gate de qualidade (mínimo de snapshots) e métrica de regressão |
| GBM in-play sem pickle | **Parcialmente resolvido** — `data/lake/artifacts/inplay_gbm.pkl` existe + 3 versões de feedback (junho) | Falta pipeline de retreino contínuo e gate de disponibilidade/freshness |
| Benchmark in-play manual | **Parcialmente resolvido (WS1)** — orquestradores `inplay-daily-report` + `inplay-weekly-report`, gates, launchd 06:12 / dom 07:18 | Resta: 7 dias consecutivos sem falha, dashboard 30d, flag `/health` |
| Código morto (`bolao_predictor`, `economics`, `baseline`) | **Pendente** — os 3 arquivos existem e têm imports ativos (`predict-round`, EV, API) | WS3 = **consolidar/deprecar**, não remover direto |
| H2H em 3 formatos / escalações em 3 fontes | **Pendente** | Workstream 3 |
| Separação do live | **Iniciada** — `live_service/` existe com `router.py` (245 linhas), `app.py`, `dependencies.py`, montável ou standalone | Workstream 4 formaliza a fronteira |

---

## Workstream 1 — Fechar o loop de validação (benchmark automatizado + métricas)

**Objetivo:** nenhuma mudança de modelo entra sem número; degradação vira alerta, não surpresa.

**Status (2026-08-05):** slice mínimo **implementado** — ver [§ WS1 — Referência operacional](#ws1--referência-operacional-implementado-2026-08-05).

### 1.1 Pipeline de avaliação diária (in-play)

- **Entrada:** `live_ticks.parquet` finalizados + odds de fechamento (via `pipelines/inplay_event_finals.py`).
- **Orquestrador:** `pipelines/inplay_daily_report.py` → CLI **`inplay-daily-report`**
  1. `full_benchmark_report(live_only=True)` — Brier modelo vs mercado por bucket de minuto
  2. `run_brier_benchmark()` — Brier estratificado (configs baseline / xG / momentum)
  3. `compute_wallet_summary` + `compute_reconciliation_metrics` — hit rate e P&L (substitui CLI `--hit-rate --pnl` ainda não exposto)
  4. `compute_operational_metrics()` — staleness, cobertura Sofascore, GBM availability (`ens_prob_l1_delta`)
- **Saída:**
  - `data/lake/reports/inplay_daily_YYYYMMDD.json`
  - append em `data/lake/metrics_history.parquet` (`report_kind=daily`)
  - baseline congelado em `data/lake/reports/inplay_baseline.json` (≥50 ticks)
- **Métricas e alvos** (do doc de precisão, §7):
  - Brier 1X2 < 0.22 (bom), sem degradação > 5% vs média móvel 7d em nenhum bucket de minuto
  - Log-loss 1X2 menor que o mercado ao vivo
  - ROI virtual > 0%, hit rate tier "forte" > 55%, cash-out accuracy > 60%
  - Operacionais: staleness < 5%, cobertura Sofascore/ScoreAlarm > 80%, GBM ativo > 90% dos ticks

### 1.2 Walk-forward semanal

- **Orquestrador:** `pipelines/inplay_weekly_report.py` → CLI **`inplay-weekly-report`**
- **Sequência padrão (domingo):**
  1. `tune-inplay --source both` — recalibra `inplay_coefficients.json` (MLE fixtures + ticks)
  2. Walk-forward via `compute_walkforward_brier` + A/B momentum (`wc_inplay_walkforward.evaluate_inplay`)
  3. `train-inplay-gbm` — retreino LightGBM walk-forward
- **Saída:**
  - `data/lake/reports/inplay_weekly_YYYYMMDD.json`
  - append em `metrics_history.parquet` (`report_kind=weekly`)
  - baseline em `data/lake/reports/inplay_weekly_baseline.json` (≥100 snapshots WF)
- **Gate:** `check_weekly_regression()` integrado ao CLI (exit 1 se Brier WF +5% vs baseline/último semanal)

### 1.3 Gates e alertas

- **Gate diário:** `scripts/check_model_regression.py` — compara relatório diário vs baseline e média 7d; exit 1 se Brier +5% ou GBM availability < 90%.
  - Teste artificial: `python scripts/check_model_regression.py --simulate-degrade 0.10`
- **Gate semanal:** embutido em `inplay-weekly-report` (mesma regra +5% no walk-forward Brier).
- **Pendente:** alerta de drift em `/health` se staleness > 5% por 2 dias seguidos.

### 1.4 Agendamento

| Job | Horário | Instalação | Log |
|-----|---------|------------|-----|
| Benchmark diário | **06:12** local | `./scripts/install-benchmark-launchd.sh` | `data/lake/logs/inplay_benchmark_daily.log` |
| Walk-forward semanal | **Dom 07:18** local | `./scripts/install-walkforward-launchd.sh` | `data/lake/logs/inplay_walkforward_weekly.log` |

Scripts auxiliares:
- `scripts/inplay_benchmark_cron.sh` — diário (report + gate)
- `scripts/inplay_walkforward_cron.sh` — semanal (tune → WF → GBM)

Variáveis `.env` opcionais:
```env
INPLAY_BENCHMARK_USER_ID=jamarorn
INPLAY_WALKFORWARD_EVAL_SEASON=2022
INPLAY_WEEKLY_SKIP_TUNE=0    # 1 = pular tune MLE
INPLAY_WEEKLY_SKIP_GBM=0     # 1 = pular retreino GBM (~10 min)
```

Relacionado (benchmark consolidado WC + histórico): `./scripts/run-model-benchmark.sh` → `run-model-benchmark`.

**Critérios de aceite**
- [ ] Relatório diário gerado sem intervenção por 7 dias consecutivos
- [x] `metrics_history.parquet` com série consultável (`report_kind` daily/weekly)
- [x] Gate de regressão reprovando downgrade artificial (`--simulate-degrade`, testes em `tests/test_inplay_daily_report.py`)
- [x] Walk-forward semanal agendado + gate semanal (`tests/test_inplay_weekly_report.py`)
- [ ] Dashboard mínimo (JSON + tabela no frontend `/config` ou MLflow) com tendência 30d

**Esforço restante WS1:** ~1–2 dias (health flag, dashboard, validar 7 dias em produção). **Risco:** baixo.

---

## Workstream 2 — Quick wins de precisão (calibrar o que já existe)

**Objetivo:** transformar os quick wins já codificados em ganhos medidos pelo Workstream 1.

### 2.1 Calibração do blending de xG ao vivo

- Hoje: `adjust_lambdas_from_xg` + modo agressivo com pesos fixos (`wc_xg_lambda_blend_weight=0.35` pré-jogo; peso w ao vivo hard-coded).
- Ação: grid de w ∈ {0.2, 0.3, 0.4, 0.5} avaliado via `inplay_benchmark` sobre ticks finalizados; escolher w por Brier, com regra de crescimento temporal (w sobe com o minuto) validada contra w fixo.
- Critério: só manter o modo agressivo ligado se vencer o modo padrão no benchmark A/B (já existe `--ab-momentum`; estender para flag de xG).

### 2.2 GBM in-play: retreino contínuo + gate

- CLI **`train-inplay-gbm`** já existe (`pipelines/wc_inplay_gbm_train.py`); retreino semanal via `inplay-weekly-report` (passo 3).
- **Pendente — gate de freshness:** se `inplay_gbm.pkl` tiver > 14 dias, logar warning explícito no relatório diário.
- **Pendente — telemetria ensemble:** log estruturado por tick quando GBM indisponível.

### 2.3 NHPP calibrado: gate de amostra mínima

- `inplay_use_calibrated_nhpp=True` já é default; adicionar fallback automático: se `inplay_coefficients.json` tiver < 500 snapshots de ticks reais, cair para o perfil default e registrar no relatório.
- Recalibrar via `tune-inplay --source both` no schedule semanal (**implementado** em `inplay-weekly-report`, passo 1).

### 2.4 Telemetria de ajustes de λ

- O `simulate_inplay` já tem `_apply_step`; garantir que **todo** ajuste (Bayes, xG, H2H, momentum, shrinkage, halftime, trailing chase) emita entrada estruturada `{step, λ_before, λ_after}` persistida no tick.
- Isso alimenta o diagnóstico de "qual ajuste está ajudando/atrapalhando" — pré-requisito para mexer no ensemble depois.

**Critérios de aceite**
- [ ] w de xG escolhido por benchmark, com resultado registrado em `data/lake/reports/`
- [x] GBM retreinado automaticamente 1x/semana (via `inplay-weekly-report`); availability medida no relatório diário
- [ ] Fallback NHPP testado (teste unitário com coefficients abaixo do mínimo)
- [ ] Ticks novos contêm trilha completa de `_apply_step`

**Esforço estimado:** 4–6 dias. **Risco:** médio — mexer em calibração sem o Workstream 1 pronto é voar às cegas; por isso a ordem é obrigatória.

---

## Workstream 3 — Limpeza (antes que o pivot multi-esporte duplique a dívida)

### 3.1 Consolidação / depreciação (não remoção direta)

| Alvo | Ação | Cuidado |
|---|---|---|
| `models/bolao_predictor.py` | Extrair heurística útil; deprecar após migrar `predict-round` | Ativo hoje — `pipelines/current_round.py` |
| `models/economics.py` | Manter — usado por EV/Kelly (futebol, basquete, beisebol) | **Não é código morto** |
| `models/baseline.py` | Mover heurística residual para módulo de liga ou `_legacy/` | Ativo — bolão, `api/routers/news.py`, benchmark |
| `models/train.py` vs `train_cli.py` | Consolidar em um só | Manter entry point do `pyproject.toml` |
| Raiz do repo | Mover `teste/`, `tsc`, `frontend@0.1.0`, zips de scrapers, `mlflow.db`/`mlruns` para fora do versionamento ou `archive/` | Atualizar `.gitignore` |

### 3.2 Unificação de H2H

- **Schema único:** adotar o formato de `wc_inplay_h2h_adjust` como canônico em `schemas/` (`H2HSummary`).
- Migração: `match_context.h2h`, `scorealarm.h2h` e `model_data.h2h_summary` passam por um único parser/adapter; formatos antigos viram `_deprecated` por 1 release e depois saem.
- Teste de contrato: fixture de match_context validando que os 3 caminhos de entrada produzem o mesmo `H2HSummary`.

### 3.3 Unificação de escalações

- Hierarquia oficial única: **FIFA → Sofascore FEPT → match_context manual**, implementada em um único resolver (`models/lineup_resolver.py` ou equivalente), consumido por pré-jogo e ao vivo.
- Remover as 3 leituras independentes; logar qual fonte venceu (telemetria de cobertura por fonte).

### 3.4 Cache de λ

- λ calculado 3x por ciclo (`goal_model_factors`, `simulate_inplay`, `inplay_from_predictor`) → cachear no predictor por `(event_id, minute_bucket)`; invalidar em gol/cartão vermelho.

**Critérios de aceite**
- [ ] `pytest` verde após remoções (~850 testes como baseline; suites dos módulos removidos saem junto)
- [ ] Grep por `bolao_predictor|economics.py|baseline.py` retorna zero imports fora de `archive/`
- [ ] Um único `H2HSummary` e um único resolver de escalação em uso nos dois fluxos
- [ ] Latência p95 do `run_live_advice` não piora (idealmente melhora com cache de λ)

**Esforço estimado:** 3–4 dias. **Risco:** baixo-médio — protegido pela suíte de testes, mas exige rodada full de `pytest` a cada remoção.

---

## Workstream 4 — Consolidar `live_service/` como fronteira oficial

**Objetivo:** transformar o início de separação em contrato formal, sem big bang.

### 4.1 Auditoria da fronteira atual

- Mapear o que `live_service/router.py` (245 linhas) já cobre vs o que ainda vive em `api/routers/live.py` e `ingest/superbet/advice.py`.
- Decisão documentada: o que migra, o que morre, o que fica compartilhado.

### 4.2 Contrato do serviço

- **Entrada:** `event_id` (+ sport). **Saída:** `LiveAdvicePayload` (schema Pydantic versionado em `schemas/live_advice.py`, `version` field).
- Dependências permitidas do live_service: leitura de artefatos versionados (`wc_predictor.pkl`, `inplay_gbm.pkl`, `inplay_coefficients.json`, pesos do ensemble) e stores de ticks. **Proibido:** importar `api/`, `pipelines/` de treino.
- Direção de dependência unidirecional: plataforma de treino publica artefatos → live_service consome. Teste de arquitetura (import-linter ou script simples de import scan) no CI.

### 4.3 Migração gradual

1. Montar `live_router` no app principal como canonical path; `api/routers/live.py` vira proxy fino (deprecação com header `X-Deprecated`).
2. Mover orquestração (`ingest/superbet/advice.py` → `live_service/orchestrator.py`) e polling (`poll_superbet_live.py` → `live_service/poller.py`).
3. Standalone real: `live_service/app.py` sobe sozinho apontando para os mesmos artefatos — pré-requisito para deploy separado futuro (Redis/fila ficam para depois, fora deste ciclo).

### 4.4 O que NÃO entra neste ciclo

- Extração para repositório/serviço deployado separado, Redis, filas, seq2seq, KXL dinâmico ao vivo, AutoML de thresholds. Tudo isso depende dos loops de validação (WS1) e da calibração (WS2) estarem estáveis.

**Critérios de aceite**
- [ ] `LiveAdvicePayload` versionado e validado por teste de contrato
- [ ] Regra de dependência (treino → artefato → live) enforceada por teste automatizado
- [ ] `live_service/app.py` standalone passando nos testes de integração principais
- [ ] Zero chamadas novas criadas em `api/routers/live.py` após a migração

**Esforço estimado:** 5–8 dias. **Risco:** médio-alto — a refatoração do orquestrador é a parte delicada; fazer por último, com métricas (WS1) para provar não-regressão.

---

## Sequenciamento e cronograma sugerido

| Semana | Foco | Entrega |
|---|---|---|
| 1 | WS1 | ~~Benchmark diário + gate~~ **feito** — validar 7 dias em produção |
| 2 | WS1 + WS2 (início) | ~~Walk-forward semanal~~ **feito** — telemetria `_apply_step`; grid de w do xG |
| 3 | WS2 | Gates freshness GBM/NHPP; decisão de pesos registrada |
| 4 | WS3 | Remoção de código morto + `H2HSummary` único |
| 5 | WS3 + WS4 (início) | Resolver de escalações + cache de λ; auditoria da fronteira live |
| 6 | WS4 | Contrato `LiveAdvicePayload` + migração do orquestrador + standalone |

**Regra de ouro do plano:** cada workstream só é "done" quando o Workstream 1 mostra, com números, que nada regrediu.

## Riscos globais

1. **Dados insuficientes de ticks** — sem volume de `live_ticks` finalizados, WS1/WS2 perdem validade estatística; mitigação: manter polling ativo e usar walk-forward em janelas maiores.
2. **Fontes externas instáveis** (Superbet intermitente, Sofascore WAF) — já mitigado parcialmente com stale fallback; métricas de cobertura/staleness do WS1 tornam o problema visível.
3. **Escopo do pivot multi-esporte vazar para dentro do plano** — mitigação: congelar novos esportes/mercados até semana 6.

---

## WS1 — Referência operacional (implementado 2026-08-05)

### Setup

```bash
pip install -e ".[dev]"

# Poll ativo (pré-requisito para live_ticks)
./scripts/install-poll-launchd.sh
# ou dev: ./scripts/dev-full.sh
```

### Benchmark diário (manual)

```bash
inplay-daily-report
inplay-daily-report --json --quiet

python scripts/check_model_regression.py
python scripts/check_model_regression.py --simulate-degrade 0.10   # deve exit 1
```

Agendar:
```bash
./scripts/install-benchmark-launchd.sh          # 06:12 diário
./scripts/install-benchmark-launchd.sh --run-now
./scripts/install-benchmark-launchd.sh --crontab   # alternativa cron
```

### Walk-forward semanal (manual)

```bash
inplay-weekly-report                            # tune + WF + GBM (~15–30 min)
inplay-weekly-report --skip-tune --skip-gbm     # só walk-forward (dev rápido)

./scripts/install-walkforward-launchd.sh        # domingo 07:18
./scripts/install-walkforward-launchd.sh --run-now
```

### Artefatos

| Arquivo | Conteúdo |
|---------|----------|
| `data/lake/reports/inplay_daily_*.json` | Brier live, brier estratificado, wallet, operacional |
| `data/lake/reports/inplay_weekly_*.json` | tune MLE, walk-forward, GBM train |
| `data/lake/metrics_history.parquet` | Série temporal (`report_kind`: `daily` \| `weekly`) |
| `data/lake/reports/inplay_baseline.json` | Baseline Brier diário congelado |
| `data/lake/reports/inplay_weekly_baseline.json` | Baseline Brier walk-forward congelado |

### CLIs relacionados (`pyproject.toml`)

| CLI | Módulo |
|-----|--------|
| `inplay-daily-report` | `pipelines/inplay_daily_report` |
| `inplay-weekly-report` | `pipelines/inplay_weekly_report` |
| `benchmark-inplay` | `pipelines/inplay_benchmark` |
| `inplay-brier-benchmark` | `pipelines/wc_inplay_brier_benchmark` |
| `tune-inplay` | `pipelines/wc_inplay_tune` |
| `train-inplay-gbm` | `pipelines/wc_inplay_gbm_train` |
| `run-model-benchmark` | `pipelines/model_benchmark_history` |

### Testes

```bash
pytest tests/test_inplay_daily_report.py tests/test_inplay_weekly_report.py -q
```
