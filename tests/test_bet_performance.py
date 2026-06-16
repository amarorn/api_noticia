"""Testes do módulo de análise de performance de apostas."""
import pytest

from models.wc_bet_performance import (
    analyze_performance,
    performance_report_to_dict,
)


@pytest.fixture
def sample_bets():
    """Conjunto de apostas finalizadas para teste."""
    return [
        {
            "id": "bet1",
            "event_name": "Brasil · Argentina",
            "home_team": "Brasil",
            "away_team": "Argentina",
            "picks": [{"market": "h2h", "outcome": "home"}],
            "stake": 20.0,
            "odds_placed": 2.10,
            "potential_return": 42.0,
            "result": "won",
            "profit": 22.0,
            "settled_at": "2026-06-01T10:00:00",
        },
        {
            "id": "bet2",
            "event_name": "Uruguai · Colômbia",
            "home_team": "Uruguai",
            "away_team": "Colômbia",
            "picks": [{"market": "totals_2.5", "outcome": "over"}],
            "stake": 15.0,
            "odds_placed": 1.85,
            "potential_return": 27.75,
            "result": "lost",
            "profit": -15.0,
            "settled_at": "2026-06-02T14:00:00",
        },
        {
            "id": "bet3",
            "event_name": "Alemanha · Japão",
            "home_team": "Alemanha",
            "away_team": "Japão",
            "picks": [{"market": "h2h", "outcome": "home"}],
            "stake": 25.0,
            "odds_placed": 1.60,
            "potential_return": 40.0,
            "result": "won",
            "profit": 15.0,
            "settled_at": "2026-06-03T16:00:00",
        },
        {
            "id": "bet4",
            "event_name": "México · Polônia",
            "home_team": "México",
            "away_team": "Polônia",
            "picks": [{"market": "btts", "outcome": "yes"}],
            "stake": 10.0,
            "odds_placed": 1.90,
            "potential_return": 19.0,
            "result": "lost",
            "profit": -10.0,
            "settled_at": "2026-06-04T18:00:00",
        },
        {
            "id": "bet5",
            "event_name": "França · Senegal",
            "home_team": "França",
            "away_team": "Senegal",
            "picks": [{"market": "h2h", "outcome": "away"}],
            "stake": 10.0,
            "odds_placed": 5.50,
            "potential_return": 55.0,
            "result": "lost",
            "profit": -10.0,
            "settled_at": "2026-06-05T20:00:00",
        },
        {
            "id": "bet6",
            "event_name": "Espanha · Marrocos",
            "home_team": "Espanha",
            "away_team": "Marrocos",
            "picks": [{"market": "totals_2.5", "outcome": "over"}],
            "stake": 12.0,
            "odds_placed": 1.75,
            "potential_return": 21.0,
            "result": "cashout",
            "profit": 2.0,
            "cashout_value": 14.0,
            "settled_at": "2026-06-06T12:00:00",
        },
    ]


class TestAnalyzePerformance:
    """Testes da função principal de análise."""

    def test_empty_bets(self):
        """Sem apostas retorna relatório vazio."""
        report = analyze_performance([])
        assert report.total_bets == 0
        assert report.roi_pct == 0

    def test_basic_metrics(self, sample_bets):
        """Métricas globais calculadas corretamente."""
        report = analyze_performance(sample_bets)
        assert report.total_bets == 6
        assert report.total_stake == 92.0  # 20+15+25+10+10+12
        # Returns: 42 + 0 + 40 + 0 + 0 + 14 = 96
        assert report.total_return == 96.0
        assert report.net_profit == 4.0
        assert report.roi_pct == pytest.approx(4.35, abs=0.1)
        # Wins: bet1, bet3 = 2 de 6
        assert report.win_rate_pct == pytest.approx(33.33, abs=0.1)

    def test_by_market(self, sample_bets):
        """Quebra por mercado identifica h2h, totals, btts."""
        report = analyze_performance(sample_bets)
        market_names = {m.market for m in report.by_market}
        assert "h2h" in market_names
        assert "totals" in market_names
        assert "btts" in market_names

    def test_h2h_performance(self, sample_bets):
        """Mercado h2h: 2 wins (42+40) de 3 apostas (20+25+10 stake)."""
        report = analyze_performance(sample_bets)
        h2h = next((m for m in report.by_market if m.market == "h2h"), None)
        assert h2h is not None
        assert h2h.total_bets == 3
        assert h2h.wins == 2
        assert h2h.losses == 1
        assert h2h.total_stake == 55.0  # 20+25+10
        assert h2h.total_return == 82.0  # 42+40+0
        # ROI = (82-55)/55 * 100 = 49.09%
        assert h2h.roi_pct == pytest.approx(49.09, abs=0.1)

    def test_by_odd_range(self, sample_bets):
        """Faixas de odd corretamente calculadas."""
        report = analyze_performance(sample_bets)
        assert len(report.by_odd_range) > 0
        # Deve ter faixa 1.50-2.00 (odds 1.60, 1.75, 1.85, 1.90) e 2.00-3.00 (2.10), e 5.00-10.0 (5.50)
        range_labels = {r.range_label for r in report.by_odd_range}
        assert "1.50–2.00" in range_labels
        assert "2.00–3.00" in range_labels
        assert "5.00–10.0" in range_labels

    def test_best_worst_market(self, sample_bets):
        """Identifica melhor e pior mercado."""
        report = analyze_performance(sample_bets)
        assert report.best_market != ""
        assert report.worst_market != ""
        # h2h tem ROI +49% (melhor)
        assert report.best_market == "h2h"

    def test_serialization(self, sample_bets):
        """Relatório serializa para dict sem erros."""
        report = analyze_performance(sample_bets)
        result = performance_report_to_dict(report)
        assert "summary" in result
        assert "by_market" in result
        assert "by_odd_range" in result
        assert "loss_patterns" in result
        assert "suggestions" in result
        assert result["summary"]["total_bets"] == 6


class TestLossPatterns:
    """Testes de detecção de padrões de perda."""

    def test_high_odds_bias_detected(self):
        """Detecta viés por odds altas com ROI negativo."""
        bets = [
            {"picks": [{"market": "h2h", "outcome": "away"}], "stake": 10, "odds_placed": 4.0,
             "potential_return": 40, "result": "lost", "settled_at": "2026-01-01"},
            {"picks": [{"market": "h2h", "outcome": "away"}], "stake": 10, "odds_placed": 5.0,
             "potential_return": 50, "result": "lost", "settled_at": "2026-01-02"},
            {"picks": [{"market": "h2h", "outcome": "away"}], "stake": 10, "odds_placed": 6.0,
             "potential_return": 60, "result": "lost", "settled_at": "2026-01-03"},
        ]
        report = analyze_performance(bets)
        pattern_types = [p.pattern_type for p in report.loss_patterns]
        assert "high_odds_bias" in pattern_types

    def test_chasing_losses_detected(self):
        """Detecta padrão de martingale."""
        bets = [
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 10, "odds_placed": 2.0,
             "potential_return": 20, "result": "lost", "settled_at": "2026-01-01T01:00:00"},
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 15, "odds_placed": 2.0,
             "potential_return": 30, "result": "lost", "settled_at": "2026-01-01T02:00:00"},
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 20, "odds_placed": 2.0,
             "potential_return": 40, "result": "lost", "settled_at": "2026-01-01T03:00:00"},
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 40, "odds_placed": 2.0,
             "potential_return": 80, "result": "lost", "settled_at": "2026-01-01T04:00:00"},
        ]
        report = analyze_performance(bets)
        pattern_types = [p.pattern_type for p in report.loss_patterns]
        assert "chasing_losses" in pattern_types

    def test_no_patterns_when_winning(self):
        """Sem padrões negativos quando tudo vai bem."""
        bets = [
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 10, "odds_placed": 1.8,
             "potential_return": 18, "result": "won", "settled_at": "2026-01-01"},
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 10, "odds_placed": 2.0,
             "potential_return": 20, "result": "won", "settled_at": "2026-01-02"},
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 10, "odds_placed": 1.9,
             "potential_return": 19, "result": "won", "settled_at": "2026-01-03"},
        ]
        report = analyze_performance(bets)
        # Pode não ter padrões negativos (ou ter apenas sugestões leves)
        critical = [p for p in report.loss_patterns if p.severity == "high"]
        assert len(critical) == 0


class TestSuggestions:
    """Testes de geração de sugestões."""

    def test_suggestions_for_negative_roi(self):
        """Gera sugestão quando ROI é negativo."""
        bets = [
            {"picks": [{"market": "h2h", "outcome": "home"}], "stake": 100, "odds_placed": 2.0,
             "potential_return": 200, "result": "lost", "settled_at": "2026-01-01"},
        ]
        report = analyze_performance(bets)
        assert report.roi_pct == -100.0
        assert any("ROI" in s for s in report.suggestions)

    def test_suggestions_for_high_avg_odd(self):
        """Gera sugestão quando odd média é muito alta."""
        bets = [
            {"picks": [{"market": "h2h", "outcome": "away"}], "stake": 10, "odds_placed": 5.0,
             "potential_return": 50, "result": "lost", "settled_at": "2026-01-01"},
            {"picks": [{"market": "h2h", "outcome": "away"}], "stake": 10, "odds_placed": 6.0,
             "potential_return": 60, "result": "lost", "settled_at": "2026-01-02"},
            {"picks": [{"market": "h2h", "outcome": "away"}], "stake": 10, "odds_placed": 4.0,
             "potential_return": 40, "result": "lost", "settled_at": "2026-01-03"},
        ]
        report = analyze_performance(bets)
        assert report.avg_odd == 5.0
        assert any("alta" in s.lower() or "odd" in s.lower() for s in report.suggestions)
