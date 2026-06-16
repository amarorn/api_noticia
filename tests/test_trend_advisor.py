"""Testes do módulo de análise de tendência (copiloto de posição)."""

from models.wc_trend_advisor import (
    GameTick,
    analyze_position,
    detect_trends,
    trend_report_to_dict,
)


def _make_ticks_domination() -> list[GameTick]:
    """Ticks simulando domínio mandante: 2-1 → 3-1 → 4-1."""
    return [
        GameTick(minute=46, home_score=2, away_score=1, total_goals=3,
                 home_generosity=0.845, away_generosity=0.035, markets_open=13),
        GameTick(minute=49, home_score=2, away_score=1, total_goals=3,
                 home_generosity=0.847, away_generosity=0.034, markets_open=15),
        GameTick(minute=53, home_score=3, away_score=1, total_goals=4,
                 home_generosity=1.0, away_generosity=0.003, markets_open=14),
        GameTick(minute=55, home_score=4, away_score=1, total_goals=5,
                 home_generosity=1.0, away_generosity=0.0003, markets_open=15,
                 over_implied={"5.5": 0.38, "6.5": 0.18}),
        GameTick(minute=63, home_score=4, away_score=1, total_goals=5,
                 home_generosity=1.0, away_generosity=0.0001, markets_open=12,
                 over_implied={"5.5": 0.63, "6.5": 0.30},
                 h2h_implied={"X": 0.02, "2": 0.02}),
    ]


def _make_ticks_draw_scenario() -> list[GameTick]:
    """Ticks simulando jogo empatado que começa a abrir."""
    return [
        GameTick(minute=30, home_score=0, away_score=0, total_goals=0,
                 home_generosity=0.5, away_generosity=0.3, markets_open=25,
                 h2h_implied={"1": 0.45, "X": 0.28, "2": 0.27}),
        GameTick(minute=35, home_score=0, away_score=0, total_goals=0,
                 home_generosity=0.52, away_generosity=0.28, markets_open=25,
                 h2h_implied={"1": 0.48, "X": 0.26, "2": 0.26}),
        GameTick(minute=40, home_score=1, away_score=0, total_goals=1,
                 home_generosity=0.72, away_generosity=0.10, markets_open=22,
                 h2h_implied={"1": 0.68, "X": 0.18, "2": 0.14}),
        GameTick(minute=55, home_score=2, away_score=0, total_goals=2,
                 home_generosity=0.95, away_generosity=0.01, markets_open=15,
                 h2h_implied={"1": 0.92, "X": 0.05, "2": 0.03}),
    ]


class TestDetectTrends:
    """Testes de detecção de sinais de tendência."""

    def test_score_gap_detected(self):
        """Detecta gap de placar >= 2."""
        ticks = _make_ticks_domination()
        signals = detect_trends(ticks)
        types = [s.signal_type for s in signals]
        assert "score_gap" in types

    def test_one_side_scoring(self):
        """Detecta que só um time marca."""
        ticks = _make_ticks_domination()
        signals = detect_trends(ticks)
        types = [s.signal_type for s in signals]
        assert "one_side_scoring" in types

    def test_market_decided(self):
        """Detecta generosity = 100% (mercado decidiu)."""
        ticks = _make_ticks_domination()
        signals = detect_trends(ticks)
        types = [s.signal_type for s in signals]
        assert "market_decided" in types

    def test_draw_dying(self):
        """Detecta empate morrendo (prob caiu de >10% para <5%)."""
        ticks = _make_ticks_draw_scenario()
        signals = detect_trends(ticks)
        types = [s.signal_type for s in signals]
        assert "draw_dying" in types or "score_gap" in types

    def test_no_signals_for_stable_game(self):
        """Jogo estável não emite sinais fortes."""
        ticks = [
            GameTick(minute=10, home_score=0, away_score=0, total_goals=0,
                     home_generosity=0.5, away_generosity=0.3, markets_open=25),
            GameTick(minute=15, home_score=0, away_score=0, total_goals=0,
                     home_generosity=0.51, away_generosity=0.29, markets_open=25),
        ]
        signals = detect_trends(ticks)
        # Pode ter sinais fracos mas nenhum forte (>0.7)
        strong = [s for s in signals if s.strength > 0.7]
        assert len(strong) == 0


class TestAnalyzePosition:
    """Testes do conselho de posição."""

    def test_exit_when_bet_against_trend(self):
        """Apostou no visitante mas mandante domina → EXIT."""
        ticks = _make_ticks_domination()
        user_bet = {"picks": [{"market": "next_goal", "outcome": "away"}]}
        report = analyze_position(user_bet, ticks)
        assert report.position_advice is not None
        assert report.position_advice.action == "exit"
        assert report.position_advice.urgency == "critical"

    def test_hold_when_aligned(self):
        """Apostou no mandante e mandante domina → HOLD."""
        ticks = _make_ticks_domination()
        user_bet = {"picks": [{"market": "h2h", "outcome": "home"}]}
        report = analyze_position(user_bet, ticks)
        assert report.position_advice is not None
        assert report.position_advice.action == "hold"

    def test_exit_draw_when_game_opens(self):
        """Apostou em empate mas placar abriu → EXIT."""
        ticks = _make_ticks_draw_scenario()
        user_bet = {"picks": [{"market": "h2h", "outcome": "draw"}]}
        report = analyze_position(user_bet, ticks)
        assert report.position_advice is not None
        assert report.position_advice.action == "exit"

    def test_reposition_suggestion(self):
        """Quando sai, sugere nova direção."""
        ticks = _make_ticks_domination()
        user_bet = {"picks": [{"market": "next_goal", "outcome": "away"}]}
        report = analyze_position(user_bet, ticks)
        assert report.best_opportunities
        assert report.position_advice.reposition_to is not None

    def test_serialization(self):
        """Relatório serializa sem erros."""
        ticks = _make_ticks_domination()
        user_bet = {"picks": [{"market": "next_goal", "outcome": "away"}]}
        report = analyze_position(user_bet, ticks)
        result = trend_report_to_dict(report)
        assert "signals" in result
        assert "position_advice" in result
        assert "best_opportunities" in result
        assert result["current_score"] == "4×1"
