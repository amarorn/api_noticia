# Glossário

| Termo | Significado |
|-------|-------------|
| **1 / X / 2** | Vitória mandante / empate / vitória visitante (bolão) |
| **λ (lambda)** | Taxa de gols esperados (parâmetro Poisson) |
| **ρ (rho)** | Parâmetro de correlação Dixon-Coles em placares baixos |
| **τ (tau)** | Fator de ajuste Dixon-Coles por placar |
| **Dixon-Coles** | Extensão do Poisson independente com correlação em 0×0, 1×0, etc. |
| **Ensemble** | Combinação ponderada de modelos (DC + logística) |
| **Brier score** | Métrica de calibração probabilística (0 = perfeito) |
| **Holdout 2022** | Copa 2022 reservada para validação sem vazamento |
| **before_date** | Recorte temporal: só jogos anteriores à data |
| **EV** | Expected Value — valor esperado de uma aposta |
| **Kelly ¼** | Fração conservadora do critério de Kelly |
| **Elo** | Rating dinâmico por vitória/empate/derrota |
| **Sigmoide** | \(\sigma(x) = 1/(1+e^{-x})\); usada no Elo e na logística |
| **Softmax** | Generalização sigmoide para múltiplas classes |
| **KXL** | Framework tático (baselines + colisão setorial) |
| **FECL** | Bloco clima/gramado (entrada dinâmica) |
| **FEJU** | Bloco arbitragem |
| **FEDE** | Bloco desfalques |
| **FEPT** | Bloco tática/titulares SofaScore |
| **FEEM** | Bloco contexto emocional/decisivo |
| **Vcar** | Vetor de carga ofensiva (KXL) |
| **Vesc** | Vetor de escape defensivo (KXL) |
| **TBRTL** | Tempo médio de posse provocado (ritmo) |
| **EACP** | Expected Attacking Collision Power |
| **Bronze/Silver/Gold** | Camadas do datalake (raw → limpo → agregado) |
| **JSONL** | Formato linha a linha para treino de LM |
| **The Odds API** | Provedor de odds esportivas ao vivo |
| **Value bet** | Aposta com EV positivo vs modelo |
| **Clean Architecture** | Domínio no centro; infra na borda |
| **Use case** | Orquestração de uma operação de negócio |
