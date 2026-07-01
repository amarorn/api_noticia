"""Schemas de Super Múltipla — cálculo de odds combinadas e bônus promo."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from schemas.user_bet import PickInput


class SuperMultiplaLegInput(PickInput):
    """Perna de múltipla com contexto Superbet e ao vivo."""

    id: str | None = Field(None, description="UUID gerado pelo cliente")
    superbet_event_id: int | None = Field(None, description="ID do evento na Superbet")
    event_name: str | None = Field(None, description="Ex.: Brasil vs Marrocos")
    selection_label: str | None = Field(None, description="Rótulo exibido na Superbet")
    is_live: bool = Field(False, description="Perna capturada em jogo ao vivo")
    minute: int | None = Field(None, ge=0, le=120, description="Minuto no momento da seleção")

    @model_validator(mode="after")
    def _require_market_odd(self) -> "SuperMultiplaLegInput":
        if self.market_odd is None or self.market_odd < 1.01:
            raise ValueError("market_odd obrigatória e >= 1.01 por perna")
        return self


class SuperMultiplaEventContext(BaseModel):
    """Placar e minuto por evento (múltiplas cross-game)."""

    superbet_event_id: int
    minute: int | None = Field(None, ge=0, le=120)
    home_score: int = Field(0, ge=0)
    away_score: int = Field(0, ge=0)
    ht_home_score: int | None = Field(None, ge=0)
    ht_away_score: int | None = Field(None, ge=0)


class SuperMultiplaCalculateRequest(BaseModel):
    """Payload para cálculo stateless de slip."""

    legs: list[SuperMultiplaLegInput] = Field(..., min_length=1)
    stake: float = Field(..., gt=0, description="Valor apostado em R$")
    bet_type: Literal["SIMPLE", "MULTIPLE"] = "MULTIPLE"
    slip_id: str | None = None
    minute: int | None = Field(None, ge=0, le=120, description="Minuto global (jogo único)")
    home_score: int = Field(0, ge=0)
    away_score: int = Field(0, ge=0)
    ht_home_score: int | None = Field(None, ge=0)
    ht_away_score: int | None = Field(None, ge=0)
    superbet_event_id: int | None = Field(None, description="Evento principal quando slip single-game")
    event_contexts: list[SuperMultiplaEventContext] = Field(default_factory=list)


class SuperMultiplaCalculateResponse(BaseModel):
    """Resultado do cálculo de múltipla."""

    slip_id: str | None = None
    total_odds: float = Field(..., gt=1)
    product_odds: float | None = Field(None, gt=1, description="Produto simples das pernas (pré-SGM)")
    pricing_mode: str = Field(
        "product",
        description="product | bet_builder_sgm | bet_builder_heuristic",
    )
    potential_payout: float = Field(..., gt=0)
    bonus_eligible: bool = False
    bonus_percentage: float = Field(0.0, ge=0)
    final_payout: float = Field(..., gt=0)
    combined_prob: float | None = Field(None, ge=0, le=1)
    combined_ev: float | None = None
    currency: str = "BRL"
    warnings: list[str] = Field(default_factory=list)
    builder_validation: dict[str, Any] | None = None
    bet_type: Literal["SIMPLE", "MULTIPLE"] = "MULTIPLE"
    legs_count: int = Field(..., ge=1)
