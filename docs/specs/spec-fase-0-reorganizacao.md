# Spec — Fase 0: Reorganização e Calibração Final

**Status:** Proposed
**Duração estimada:** 3 dias
**Owner:** amaro
**Depende de:** —
**Habilita:** Fases 1, 2, 3

---

## 1. Goal

Tornar o pipeline de treino **reproduzível por um único comando** e **calibrar as probabilidades finais** do ensemble (que hoje são medidas mas não corrigidas).

## 2. Non-goals

- ❌ Não muda matemática do modelo (Poisson, Dixon-Coles, momentum continuam iguais).
- ❌ Não toca em `wc_inplay.py`.
- ❌ Não adiciona novas features.

## 3. Motivação

- `models/train.py` (61 linhas) é só um stub Unsloth — o treino real de Dixon-Coles/Logística está espalhado em `dixon_coles_wc.py:fit` e `logistic_wc.py:fit`. Não há entrypoint único.
- `wc_calibration.py:57` **mede** descalibração via `calibration_by_predicted_class` mas **não aplica** correção. Se o modelo diz 70% e acerta 60%, a saída continua 70%.

## 4. Success Metrics

| Métrica | Baseline (medir antes) | Alvo |
|---|---|---|
| Comando único `python -m models.train` treina tudo | ❌ não existe | ✅ existe |
| ECE (Expected Calibration Error) ensemble | medir | reduzir ≥ 30% |
| Brier ensemble (walk-forward Copa) | medir | manter ou melhorar |
| MLflow run registrado por execução | parcial | 100% |

## 5. Design Técnico

### 5.1 Novo entrypoint `models/train.py`

Substitui o stub atual. Orquestra:

```python
def train_wc_full(
    *,
    validation_season: int = 2022,
    run_calibration: bool = True,
    log_mlflow: bool = True,
) -> dict:
    fixtures = load_wc_fixtures()
    with mlflow.start_run(run_name=f"wc_full_{validation_season}"):
        # 1. Dixon-Coles (estima rho via MLE no holdout)
        dixon = DixonColesWcModel().fit(fixtures, holdout_season=validation_season)
        # 2. Logística (features + holdout)
        logistic = WcLogisticModel().fit(fixtures, holdout_season=validation_season)
        # 3. Ensemble colaborativo (otimiza pesos)
        collab = CollaborativeWcModel(dixon_coles=dixon).fit(
            fixtures, validation_season=validation_season, logistic_model=logistic
        )
        # 4. Calibração isotônica/Platt em cima das probas finais
        if run_calibration:
            calibrator = ProbabilityCalibrator().fit(collab, fixtures, validation_season)
            collab.attach_calibrator(calibrator)
        # 5. Persiste artefato
        artifact = WcArtifact.from_models(dixon, logistic, collab)
        artifact.save()
        return artifact.metrics
```

### 5.2 Novo módulo `models/wc_calibrator.py`

```python
@dataclass
class ProbabilityCalibrator:
    """Platt scaling multinomial sobre saídas 1/X/2 do ensemble.

    Treina um regressor logístico (3 classes) usando como input as 3
    probabilidades raw do ensemble e como target o resultado real.
    """
    coef_: np.ndarray | None = None
    intercept_: np.ndarray | None = None

    def fit(self, collab, fixtures, validation_season): ...
    def transform(self, probs: dict[str, float]) -> dict[str, float]: ...
```

Alternativa: **isotonic regression por classe** (mais flexível, menos paramétrico). Decisão: começar com Platt (3 params), se ECE não cair o suficiente, migrar para Isotonic.

### 5.3 Mudanças em arquivos existentes

| Arquivo | Mudança |
|---|---|
| `models/train.py` | Reescrever (de 61 → ~120 linhas) |
| `models/wc_collaborative.py` | Adicionar `attach_calibrator()` + aplicar no `predict()` se presente |
| `models/wc_artifact.py` | Serializar calibrator junto |
| `pipelines/wc_calibration.py` | Adicionar ECE no relatório (hoje só tem bins) |
| `pipelines/mlflow_tracking.py` | Helpers `log_calibration_curve()` |

### 5.4 Fallback de produção

Se `calibrator` não está presente no artefato carregado, `predict()` retorna probas raw (comportamento atual). Garantia: produção não quebra durante rollout.

## 6. Plano de Implementação

### Dia 1
- [ ] Criar `models/wc_calibrator.py` com `ProbabilityCalibrator` (Platt 3-class).
- [ ] Test unitário: treinar em dados sintéticos, verificar ECE diminui.
- [ ] Adicionar função `expected_calibration_error()` em `models/eval_metrics.py`.

### Dia 2
- [ ] Reescrever `models/train.py` com orquestração completa.
- [ ] Estender `WcArtifact` para persistir calibrator (pickle versionado).
- [ ] Estender `wc_calibration.py` para logar ECE pré e pós calibração.

### Dia 3
- [ ] MLflow: logar todos os artefatos + curva de calibração como PNG.
- [ ] Validar walk-forward: `python -m pipelines.wc_walkforward` com modelo calibrado.
- [ ] Atualizar `docs/modelos-preditivos.md` com o novo entrypoint.

## 7. Test Plan

### Unit tests
- `tests/test_wc_calibrator.py`:
  - Calibrator não-treinado retorna identidade.
  - Após `fit`, soma das 3 probas = 1.0.
  - Em dataset onde modelo é overconfident, ECE pós < ECE pré.

### Integration test
- `python -m models.train --validation-season 2022` roda end-to-end e produz artefato válido.

### Validação manual
- Plotar curva de calibração antes/depois (reaproveitar `calibration_chart` de `wc_calibration.py:83`).
- Confirmar que para `prob_predita ∈ [0.5, 0.7]`, `freq_observada` está próxima da diagonal.

## 8. Rollback Plan

- Calibrator é **opcional** no artefato. Para reverter: deletar key `calibrator` do artefato persistido — `predict()` cai para raw automático.
- Versionar artefato como `wc_artifact_v2.json`; manter `wc_artifact_v1.json` (sem calibrator) como fallback.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Platt scaling overfit no holdout pequeno | Usar K-fold dentro do holdout para fit do calibrator |
| ECE não diminui (modelo já calibrado) | Reportar mesmo assim — vale como confirmação. Não bloqueia fase 1. |
| Persistência quebra carregamento antigo | Adicionar campo `version` no artefato e código de migração |

## 10. Definition of Done

- [ ] `python -m models.train` treina tudo em < 5 min e produz `wc_artifact_v2.json`.
- [ ] MLflow run mostra: rho, weights, Brier (pré/pós), ECE (pré/pós), curva calibração.
- [ ] Walk-forward com calibrator não piora Brier > 0.001.
- [ ] Documentação atualizada.
- [ ] PR mergeada e produção rodando v2.
