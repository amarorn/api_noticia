"""Validação de propostas de combo enviadas pelo frontend (modelo × mercado)."""

from __future__ import annotations

from schemas.user_bet import UserOpenBetRequest


class ComboProposalValidationError(ValueError):
    """Proposta não atende critérios mínimos de modelo + mercado."""


def _combined_ev_from_request(req: UserOpenBetRequest) -> float:
    if req.combined_ev is not None:
        return float(req.combined_ev)
    prob = 1.0
    for pick in req.picks:
        if pick.model_prob is None:
            raise ComboProposalValidationError(
                "Probabilidade do modelo ausente — proposta deve usar nossos dados in-play ou KXL."
            )
        prob *= float(pick.model_prob)
    return prob * float(req.odds_placed) - 1.0


def validate_combo_proposal(req: UserOpenBetRequest) -> None:
    """Garante que propostas da estação cruzam modelo interno com odd de mercado."""
    if req.source != "bolao_proposal":
        return

    if not req.picks:
        raise ComboProposalValidationError("Proposta sem palpites.")

    for idx, pick in enumerate(req.picks, start=1):
        if pick.market_odd is None or pick.market_odd <= 1.0:
            raise ComboProposalValidationError(
                f"Perna {idx}: odd de mercado ausente — use linha disponível na Superbet."
            )
        if pick.model_prob is None or pick.model_prob <= 0:
            raise ComboProposalValidationError(
                f"Perna {idx}: probabilidade do modelo ausente — baseie-se nos nossos dados."
            )
        if pick.expected_value is not None and pick.expected_value <= 0:
            raise ComboProposalValidationError(
                f"Perna {idx}: EV não positivo ({pick.expected_value:.1%}) — sem edge vs mercado."
            )

    combined_ev = _combined_ev_from_request(req)
    if combined_ev <= 0:
        raise ComboProposalValidationError(
            f"EV combinado {combined_ev:.1%} — só envie quando modelo × odd Superbet tiver edge."
        )


__all__ = ["ComboProposalValidationError", "validate_combo_proposal"]
