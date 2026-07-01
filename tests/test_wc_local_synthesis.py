"""Testes para models/wc_local_synthesis.py."""
from __future__ import annotations


from models.wc_local_synthesis import (
    _build_arbitro_from_context,
    _build_escalacao_from_context,
    _build_fatores_from_context,
    _build_mercados_from_model,
    _build_picks_from_model,
    _build_placar_provavel,
    _build_resumo_executivo,
    _build_riscos_from_context,
    generate_local_synthesis,
)


class TestBuildPicksFromModel:
    def test_basic_picks(self):
        model_data = {
            "ticket": {
                "singles": [
                    {"label": "Vitória Brasil", "market": "1", "model_prob": 0.72, "fair_odd": 1.39},
                    {"label": "Empate", "market": "X", "model_prob": 0.18, "fair_odd": 5.56},
                    {"label": "Vitória Haiti", "market": "2", "model_prob": 0.10, "fair_odd": 10.0},
                    {"label": "Mais de 2.5 gols", "market": "over_2_5", "model_prob": 0.58, "fair_odd": 1.72},
                    {"label": "Ambas marcam", "market": "btts", "model_prob": 0.48, "fair_odd": 2.08},
                ],
                "combo": {"label": "Brasil vence + Over 2.5", "model_prob": 0.42, "fair_odd": 2.38},
            }
        }
        picks = _build_picks_from_model(model_data)
        assert len(picks) > 0
        assert picks[0]["aposta"] == "Vitória Brasil"
        assert picks[0]["nivel_confianca"] == "Alta"

    def test_no_combo_if_low_prob(self):
        model_data = {
            "ticket": {
                "singles": [
                    {"label": "Vitória Brasil", "market": "1", "model_prob": 0.55, "fair_odd": 1.82},
                ],
                "combo": {"label": "Combo", "model_prob": 0.20, "fair_odd": 5.0},
            }
        }
        picks = _build_picks_from_model(model_data)
        combo_picks = [p for p in picks if "Combo" in p["aposta"]]
        assert len(combo_picks) == 0


class TestBuildEscalacaoFromContext:
    def test_with_lineups(self):
        ctx = {
            "lineups": {
                "brasil": {
                    "gk": "Alisson",
                    "def": ["Danilo", "Marquinhos", "Gabriel", "Douglas"],
                    "mid": ["Casemiro", "Bruno", "Paqueta"],
                    "fwd": ["Raphinha", "Vini", "Endrick"],
                    "doubts": ["Neymar"],
                }
            }
        }
        esc = _build_escalacao_from_context(ctx, "brasil")
        assert esc["status"] == "Provável"
        assert "Neymar" in esc["lesoes_suspensoes"]

    def test_no_context(self):
        esc = _build_escalacao_from_context(None, "home")
        assert esc["status"] == "Não disponível"


class TestBuildArbitroFromContext:
    def test_with_referee(self):
        ctx = {
            "referee_name": "Hernandez",
            "referee_card_lambda": 5.46,
            "referee_profile": "punitivista",
            "referee_nationality": "Espanha",
        }
        arb = _build_arbitro_from_context(ctx)
        assert arb["nome"] == "Hernandez"
        assert "punitivista" in arb["perfil"]
        assert arb["card_lambda"] == 5.46

    def test_no_referee(self):
        arb = _build_arbitro_from_context(None)
        assert arb["nome"] == "Não divulgado"


class TestBuildFatoresFromContext:
    def test_with_h2h(self):
        ctx = {"h2h_total_games": 5, "h2h_home_wins": 5}
        model_data = {"confidence": 0.7, "prediction": "1"}
        fatores = _build_fatores_from_context(ctx, model_data)
        assert any("Dominância" in f for f in fatores)

    def test_with_referee(self):
        ctx = {
            "referee_name": "Hernandez",
            "referee_card_lambda": 5.46,
            "referee_profile": "punitivista",
        }
        model_data = {"confidence": 0.5, "prediction": "1"}
        fatores = _build_fatores_from_context(ctx, model_data)
        assert any("punitivista" in f for f in fatores)


class TestBuildRiscosFromContext:
    def test_low_confidence(self):
        model_data = {"confidence": 0.25, "prediction": "X"}
        riscos = _build_riscos_from_context(None, model_data)
        assert any("Baixa confiança" in r for r in riscos)

    def test_synthetic_pitch(self):
        ctx = {"pitch_type": "sintetico"}
        model_data = {"confidence": 0.6, "prediction": "1"}
        riscos = _build_riscos_from_context(ctx, model_data)
        assert any("sintético" in r for r in riscos)


class TestBuildMercadosFromModel:
    def test_home_favorite(self):
        model_data = {
            "prob_home": 0.72,
            "prob_draw": 0.18,
            "prob_away": 0.10,
            "ticket": {
                "singles": [
                    {"market": "over_2_5", "model_prob": 0.58},
                    {"market": "btts", "model_prob": 0.48},
                ]
            }
        }
        mercados = _build_mercados_from_model(model_data)
        assert "Favorito mandante" in mercados["resultado"]
        assert "Over 2.5" in mercados["over_under"]


class TestBuildResumoExecutivo:
    def test_basic(self):
        model_data = {"prediction": "1", "confidence": 0.72, "expected_goals": "2.5x0.8"}
        ctx = {"competition": "Copa do Mundo 2026"}
        resumo = _build_resumo_executivo("Brasil", "Haiti", model_data, ctx)
        assert "Brasil x Haiti" in resumo
        assert "Copa do Mundo 2026" in resumo


class TestBuildPlacarProvavel:
    def test_with_scorelines(self):
        model_data = {"top_scorelines": [{"score": "3x0", "prob": 0.25}, {"score": "2x0", "prob": 0.20}]}
        placar = _build_placar_provavel(model_data)
        assert placar == "3x0"

    def test_without_scorelines(self):
        model_data = {"expected_goals": "2.1x0.7"}
        placar = _build_placar_provavel(model_data)
        assert placar == "2.1x0.7"


class TestGenerateLocalSynthesis:
    def test_full_synthesis(self):
        model_data = {
            "prob_home": 0.72,
            "prob_draw": 0.18,
            "prob_away": 0.10,
            "confidence": 0.72,
            "prediction": "1",
            "expected_goals": "2.5x0.8",
            "poisson_score": "3x0",
            "h2h_summary": "Brasil 3x0 nos últimos 3",
            "ticket": {
                "singles": [
                    {"label": "Vitória Brasil", "market": "1", "model_prob": 0.72, "fair_odd": 1.39},
                    {"label": "Mais de 2.5 gols", "market": "over_2_5", "model_prob": 0.58, "fair_odd": 1.72},
                ],
                "combo": None,
            },
            "top_scorelines": [{"score": "3x0", "prob": 0.25}],
        }
        ctx = {
            "referee_name": "Hernandez",
            "referee_card_lambda": 5.46,
            "referee_profile": "punitivista",
            "h2h_total_games": 3,
            "h2h_home_wins": 3,
            "competition": "Copa do Mundo 2026",
        }
        synth = generate_local_synthesis("Brasil", "Haiti", model_data, ctx)
        assert synth is not None
        assert synth["favorito"] == "Brasil"
        assert synth["confianca_geral"] == "Alta"
        assert len(synth["picks_recomendados"]) > 0
        assert synth["arbitro"]["nome"] == "Hernandez"
        assert synth["_source"] == "local_synthesis"
        assert "Análise gerada localmente" in synth["nota_final"]

    def test_without_context(self):
        model_data = {
            "prob_home": 0.55,
            "prob_draw": 0.25,
            "prob_away": 0.20,
            "confidence": 0.55,
            "prediction": "1",
            "expected_goals": "1.8x1.0",
            "ticket": {"singles": [], "combo": None},
        }
        synth = generate_local_synthesis("Brasil", "Haiti", model_data, None)
        assert synth is not None
        assert synth["favorito"] == "Brasil"
        assert synth["confianca_geral"] == "Média"
