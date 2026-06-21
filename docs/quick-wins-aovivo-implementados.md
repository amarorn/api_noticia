# Quick Wins do Modelo Ao Vivo — Implementados

> Data: 2026-06-21
> Objetivo: melhorar a precisão do modelo in-play com mudanças rápidas e de baixo risco.

---

## Resumo das mudanças

| # | Quick win | Status | Arquivos alterados |
|---|-----------|--------|--------------------|
| 1 | Habilitar NHPP calibrado com fallback seguro | ✅ | `config.py`, `pipelines/wc_intensity_profile.py` |
| 2 | Isolar GBM não-treinado e logar warning | ✅ | `models/wc_inplay.py` |
| 3 | Integrar xG acumulado ao vivo no ajuste de λ | ✅ | `config.py`, `models/wc_inplay_live_adjust.py`, `models/wc_inplay.py` |
| 4 | Melhorar logging de ajustes de λ (antes/depois) | ✅ | `models/wc_inplay.py` |
| 5 | Rodar benchmark A/B de baseline | ✅ | `data/lake/reports/inplay_benchmark_baseline_20260621.json` |

---

## 1. NHPP calibrado habilitado por padrão

### O que mudou
- `config.py`: `inplay_use_calibrated_nhpp` agora é `True` por padrão.
- `pipelines/wc_intensity_profile.py`: adicionada validação de `n_observations >= 500` e validação do perfil antes de usar o calibrado.

### Por quê
O arquivo `data/lake/artifacts/inplay_coefficients.json` possui **15.660 observações** e holdout Brier de 0.1197 vs baseline 0.1207. O perfil calibrado estava desperdiçado porque a flag estava desligada.

### Fallback
Se o arquivo não existir, tiver menos de 500 observações, perfil inválido ou **não respeitar a propriedade empírica de intensidade crescente no final do jogo**, o sistema volta automaticamente para o perfil NHPP padrão da literatura.

> ⚠️ O arquivo `inplay_coefficients.json` atual possui 15.660 observações, mas seu perfil NHPP calibrado decai no final do jogo (bucket 75-90 com peso 0.43). Por segurança, ele foi rejeitado e o perfil padrão está sendo usado. Recomenda-se revisar o treino do NHPP.

---

## 2. GBM não-treinado agora loga warning

### O que mudou
- Adicionado logger `structlog` em `models/wc_inplay.py`.
- Na função `simulate_inplay_ensemble`, quando o GBM não está treinado ou falha, um warning estruturado é emitido com:
  - times, minuto, caminho do artefato e erro.

### Por quê
Antes o GBM era silenciosamente desligado, dificultando saber quando a perna mais rica em features do ensemble estava inativa.

---

## 3. xG acumulado ao vivo ajusta λ

### O que mudou
- Nova função `adjust_lambdas_from_xg` em `models/wc_inplay_live_adjust.py`.
- Integrada em `models/wc_inplay.simulate_inplay` após o ajuste de live_stats.
- Novas configs em `config.py`:
  - `inplay_xg_lambda_adjust: bool = True`
  - `inplay_xg_max_shift: float = 0.25`
  - `inplay_xg_weight_max: float = 0.40`

### Como funciona
```
λ_obs = xG_acumulado / (minutos decorridos / 90)
λ_novo = w × λ_obs + (1 - w) × λ_atual
w = min(0.40, 0.40 × (fração decorrida)² / 0.5)
```

O shift é limitado a ±25% do λ atual para evitar overreaction.

### Exemplo real
No teste `Brasil 1×0 Argentina, minuto 60`:
- λ_home pré-jogo: 1.4
- Após Bayesian + live_stats: 1.515
- Após xG (1.8 xG acumulado): **1.893** (+25%)

Isso significa que o modelo agora "enxerga" que o time da casa está criando chances além do esperado.

---

## 4. Logging de ajustes de λ melhorado

### O que mudou
- Cada passo de ajuste em `simulate_inplay` agora registra:
  - `lambda_before_home/away`
  - `lambda_after_home/away`
  - `delta_home_pct/away_pct`
- Adicionado log debug `inplay_lambda_adjustments` com resumo quando há ajustes.

### Exemplo de saída
```json
{
  "step": "live_xg",
  "lambda_before_home": 1.515,
  "lambda_before_away": 0.818,
  "lambda_after_home": 1.893,
  "lambda_after_away": 0.847,
  "delta_home_pct": 25.0,
  "delta_away_pct": 3.56,
  "source": "live_xg",
  "live_weight": 0.356,
  "home_xg": 1.8,
  "away_xg": 0.6
}
```

---

## 5. Benchmark de baseline

### Comando usado
```bash
python3 -m pipelines.inplay_benchmark --ab-momentum --json
```

### Resultados — Live ticks (11 eventos, 176 ticks)
| Métrica | Valor |
|---------|-------|
| Brier modelo | 0.15015 |
| Brier mercado | 0.14811 |
| Delta | +0.00205 (mercado levemente melhor) |
| Accuracy | 65.91% |

### Resultados — Walk-forward 2022 (515 jogos, 5.796 amostras)
| Variante | Brier |
|----------|-------|
| Sem momentum | 0.125797 |
| Momentum default | 0.126193 |
| **Momentum calibrado** | **0.124260** |

> O momentum calibrado é o melhor dos três. O momentum default piora em relação à ausência de momentum.

### Reconciliação de apostas reais
| Métrica | Valor |
|---------|-------|
| Bilhetes | 486 |
| Match rate | 46.9% |
| Hit rate | 28.9% |
| P&L | -R$ 889.86 |

> O hit rate baixo e P&L negativo indicam que as recomendações ainda precisam de ajustes nos thresholds de negócio (não no núcleo probabilístico).

---

## Próximos passos recomendados

Após os quick wins, as alavancas de maior impacto são:

1. **Treinar o GBM in-play com labels reais** (`próximo gol em 10 min`). Hoje o GBM existe como artefato, mas não há garantia de que está sendo retreinado com os live_ticks.
2. **Reformular o ensemble** com stacking aprendido em vez de pesos fixos por bucket.
3. **Ajustar thresholds de negócio** (`live_min_edge_pp`, `live_midgame_ev_multiplier`) para melhorar hit rate e P&L.
4. **Integrar substituições** do feed ao vivo no momentum.
5. **Separar o módulo ao vivo** em `live/` com fronteira clara.

---

## Arquivos modificados

- `config.py`
- `pipelines/wc_intensity_profile.py`
- `models/wc_inplay.py`
- `models/wc_inplay_live_adjust.py`
- `docs/quick-wins-aovivo-implementados.md` (este arquivo)
- `data/lake/reports/inplay_benchmark_baseline_20260621.json`
