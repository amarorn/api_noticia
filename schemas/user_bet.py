"""Schema de entrada para apostas do usuário com suporte a combos."""
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PickInput(BaseModel):
    """Um palpite individual dentro de uma simples ou múltipla."""

    market: str = Field(..., description="Tipo de mercado: h2h | over_2_5 | btts | next_goal | btts_any_half | combo_over_btts")
    outcome: str = Field(..., description="Palpite: 1|X|2|yes|no|home|away")
    target_value: str | None = Field(None, description="Valor de referência: total de gols, intervalo de tempo, etc.")


class UserOpenBetRequest(BaseModel):
    """Payload enviado pela extensão Chrome ou formulário ao cadastrar aposta do usuário.

    Suporta simples, combos (bilhete com vários palpites) e bets ao vivo da Superbet.
    """

    id: str | None = Field(None, description="ID gerado pelo cliente (UUID/browser) para deduplicação")
    superbet_event_id: int | None = Field(None, description="ID do evento na Superbet, se conhecido")
    event_name: str = Field(..., description="Nome do evento: 'Japão vs África do Sul'")
    home_team: str = Field(..., description="Mandante")
    away_team: str = Field(..., description="Visitante")
    picks: list[PickInput] = Field(..., min_length=1, description="Um ou mais palpites")
    stake: float = Field(..., gt=0, description="Valor apostado em R$")
    odds_placed: float = Field(..., gt=1, description="Odd total da entrada")
    potential_return: float = Field(..., gt=0, description="Retorno potencial (ganho bruto)")
    cashout_value: float | None = Field(None, ge=0, description="Valor atual de cash-out disponível")
    ticket_code: str | None = Field(None, description="Código do bilhete na Superbet (ex: 892P-1YINSZ)")
    source: str = Field("extension", description="Origem: extension | manual")
    captured_at: str | None = Field(None, description="ISO timestamp de quando a aposta foi capturada")
    minute: int | None = Field(
        None,
        ge=0,
        le=120,
        description="Minuto do jogo no momento do cadastro (para guardrails P0)",
    )

    @model_validator(mode="after")
    def _check_combo_odds(self) -> "UserOpenBetRequest":
        # Se há picks múltiplos, a odd total deve ser aproximadamente o produto das odds parciais
        # Esta validação é leve: só garante consistência básica
        if len(self.picks) > 1 and self.odds_placed < 1.5:
            raise ValueError("odd total inválida para múltipla (deve ser > 1.5)")
        return self


class UserOpenBetResponse(BaseModel):
    """Resposta de cadastro / consulta de apostas abertas."""

    id: str
    bets: list[dict[str, Any]] = Field(default_factory=list, description="Lista de apostas ativas")
    message: str = "ok"


class SettledBetInput(BaseModel):
    """Payload de uma aposta liquidada capturada pela extensão."""

    id: str
    event_name: str = ""
    home_team: str = ""
    away_team: str = ""
    picks: list[PickInput] = Field(default_factory=list)
    stake: float = Field(0, ge=0)
    odds_placed: float = Field(0, ge=0)
    potential_return: float = Field(0, ge=0)
    result: str = Field(..., description="won | lost | cashout | void")
    profit: float = Field(0, description="Lucro líquido (negativo se perdeu)")
    cashout_value: float | None = None
    ticket_code: str | None = None
    source: str = "superbet_extension"
    placed_at: str = ""
    settled_at: str = ""
    superbet_event_id: int | None = None
    final_score: str | None = None


class SettledBetsBatchRequest(BaseModel):
    """Batch de apostas finalizadas para upload."""

    bets: list[SettledBetInput] = Field(..., min_length=1)
