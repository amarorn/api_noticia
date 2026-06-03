# Motor KXL — Método de Colisão (Copa 2026)

Documentação do módulo `pipelines/wc_kxl_collision.py`, alinhada ao PDF *DADOS PARCEIAIS PARA FORMULAS VETORES ATUALIZADO* e aos baselines em `data/wc/team_baselines.json`.

## Origem das regras

| Elemento | Fonte |
|----------|--------|
| Pilares Energia / Espaço / Tempo | PDF (introdução) |
| Overrides chuva, árbitro, gap SofaScore | PDF (página 2–3) |
| Baselines EA, EC, ED, EG, TTBP, FSC | TXT/PDF (48 seleções) |
| Fórmula fechada de λ (gols) e 30 quadrantes completos | **Não constam no material** — implementação inferida (3 setores × 3 setores) |

Não foi encontrado repositório externo com implementação de colisão; este módulo é a referência no `api_noticia`.

## Pilares

### 1. Energia (`E`)

Força do elenco no dia (SofaScore) ou proxy do baseline:

```
E = média(nota_sofascore atacantes) / 7.5     (se FEPT enviado)
E = 0.35×(ECDC/12) + 0.35×(EAGD/55) + 0.30×(ECCH/18)   (senão)
```

### 2. Espaço — colisão setorial (`C`)

Três fendas zonais (proxy dos 30 quadrantes do PDF):

```
C_{h→a,s} = DNA_{h,s} × Perm_{a,s} × (1 + EAGD_h/100 × EGSD_a/100)
```

com `s ∈ {direita, esquerda, meio}`.

Pressão espacial mandante:

```
S_h = Σ_s C_{h→a,s} / 3
```

### 3. Tempo — TBRTL (`T`)

`TTBP_provocado_segundos` limita ritmo (Folha Branca):

```
T = clamp(TTBP / 1800, 0.7, 1.15)
T_draw = 1 + |TTBP_h − TTBP_a| / 1800 × 0.15    (empate se ritmos divergem)
```

## Vetores do PDF

### Vcar (vetor de carga ofensiva)

```
Vcar_raw_h = (0.45×S_h + 0.35×E_h + 0.20×(ECCH_h/18)) × T_h × FSC_h × M_h
```

`M_h` = produto dos moduladores dinâmicos (FECL, FEJU, FEDE, FEPT, FEEM).

Regras do PDF sobre `M`:

- Chuva/umidade alta: `ECPC × 0.90`, `Vesc × 1.12` (aplicado no vetor defensivo do adversário)
- Juiz punitivista: `Vcar × 1.25`
- Juiz pacificador: `Vcar × 0.85`
- Gap nota atacante − defensor ≥ 0,8: atrito disciplinar +15% → favorece empate

### Vesc (vetor de escape / absorção defensiva)

```
Vesc_a = (0.40×EDDF_a/26 + 0.35×(12−EDCT_a)/12 + 0.25×GK_a) × M_esc_a
```

`GK_a = (100 − EGSD_a) / 100`.

Efetividade ofensiva após colisão:

```
V_eff_h = Vcar_raw_h × (1 − 0.35 × Vesc_a)
```

## Probabilidades 1 / X / 2

```
Δ = V_eff_h − V_eff_a
P(1) = σ(4Δ) × (1 − P_draw)
P(2) = (1 − σ(4Δ)) × (1 − P_draw)
P_draw = clamp(0.22 − |Δ|×0.35 + caos×0.05 + atrito×0.04, 0.08, 0.38)
```

`σ` = função logística. Normalização final para soma 1.

## Integração no palpite

```
P_final = 0.75 × P_ensemble + 0.25 × P_colisão
```

Depois: overrides dinâmicos da Fase 2 (se `kxl_match` enviado), que podem ajustar probabilidades já blendadas.

## API

- Código: `pipelines/wc_kxl_collision.py`
- Função principal: `collision_predict(home, away, kxl_match=None)`
- Breakdown JSON: `model_breakdown.kxl_collision` com `vcar`, `vesc`, `setores`, `moduladores`

## Letalidade × Goleiro (4 vias)

Para cada via de finalização do ataque e fraqueza correspondente do GK adversário:

```
Pressão_m = (EAG_m / 55) × (EG_m / 100)
```

Vias: cabeça (EAGC×EGCF), fora (EAGF×EGSF), área (EAGD×EGSD), bola parada (EABP×média fraquezas GK).

`Vcar` recebe `× (1 + 0.18 × índice_dominante)`.

**EACP** (chances perdidas/jogo): média > 1,55 entre os dois times aumenta levemente `P(empate)`.

## Limitações conhecidas

1. Sem mapa completo dos 30 quadrantes — apenas 3 setores (dir / esq / meio).
2. `Vcar`/`Vesc` do PDF aparecem como conceitos; coeficientes numéricos além dos multiplicadores 1.25/0.85/1.12 foram calibrados para escala 0–2.
3. Margem de erro alvo do PDF (±5–8%) não foi validada em backtest neste repositório.
