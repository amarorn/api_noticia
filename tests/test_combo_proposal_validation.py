"""Validação modelo × mercado para propostas de combo."""

from __future__ import annotations

import pytest

from models.combo_proposal import ComboProposalValidationError, validate_combo_proposal
from schemas.user_bet import PickInput, UserOpenBetRequest


def _req(**kwargs) -> UserOpenBetRequest:
    base = {
        "event_name": "A × B",
        "home_team": "A",
        "away_team": "B",
        "picks": [
            PickInput(
                market="h2h",
                outcome="X",
                model_prob=0.6,
                market_odd=1.5,
                expected_value=0.1,
            ),
            PickInput(
                market="over_2_5",
                outcome="no",
                model_prob=0.7,
                market_odd=1.4,
                expected_value=0.05,
            ),
        ],
        "stake": 10.0,
        "odds_placed": 2.1,
        "potential_return": 21.0,
        "source": "bolao_proposal",
        "combined_ev": 0.08,
        "combined_prob": 0.42,
    }
    base.update(kwargs)
    return UserOpenBetRequest(**base)


def test_validate_combo_proposal_ok():
    validate_combo_proposal(_req())


def test_validate_combo_proposal_rejects_missing_market_odd():
    picks = [
        PickInput(market="h2h", outcome="X", model_prob=0.6),
    ]
    with pytest.raises(ComboProposalValidationError, match="mercado"):
        validate_combo_proposal(
            _req(picks=picks, odds_placed=1.8, potential_return=18.0, combined_ev=0.05),
        )


def test_validate_combo_proposal_rejects_negative_combined_ev():
    with pytest.raises(ComboProposalValidationError, match="EV combinado"):
        validate_combo_proposal(_req(combined_ev=-0.05))
