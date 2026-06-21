"""Schema para resposta do otimizador de bilhetes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TicketLeg(BaseModel):
    """Perna de um bilhete otimizado."""

    market: str
    outcome: str
    label: str
    model_prob: float = Field(..., ge=0.0, le=1.0)
    market_odd: float = Field(..., ge=1.01)
    expected_value: float
    edge_pp: float
    kelly_quarter: float
    classification: str


class TicketValidation(BaseModel):
    """Resultado da validação do bilhete."""

    valid: bool
    errors: list[dict]
    warnings: list[dict]
    legs_count: int


class OptimizedTicket(BaseModel):
    """Bilhete otimizado retornado pelo modelo."""

    legs: list[TicketLeg]
    combined_odd: float
    combined_prob: float
    combined_ev: float
    correlation_penalty: float
    score: float
    stake_brl: float
    stake_pct: float
    period_mix: str  # "1h" | "2h" | "ft" | "mixed"
    n_legs: int
    valid: bool
    validation: TicketValidation


class OptimizedTicketsResponse(BaseModel):
    """Resposta do endpoint de bilhetes otimizados."""

    event_id: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    minute: int | None = None
    home_score: int = 0
    away_score: int = 0
    tickets_1h: list[OptimizedTicket] = Field(default_factory=list)
    tickets_2h: list[OptimizedTicket] = Field(default_factory=list)
    tickets_ft: list[OptimizedTicket] = Field(default_factory=list)
    tickets_mixed: list[OptimizedTicket] = Field(default_factory=list)
    total_tickets: int = 0
    generated_at: str | None = None


__all__ = [
    "TicketLeg",
    "TicketValidation",
    "OptimizedTicket",
    "OptimizedTicketsResponse",
]
