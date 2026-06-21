"""Schema de entrada para apostas do usuário com suporte a combos."""
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PickInput(BaseModel):
    """Um palpite individual dentro de uma simples ou múltipla."""

    market: str = Field(..., description="Tipo de mercado: h2h | over_2_5 | btts | next_goal | btts_any_half | combo_over_btts")
    outcome: str = Field(..., description="Palpite: 1|X|2|yes|no|home|away")
    target_value: str | None = Field(None, description="Valor de referência: total de gols, intervalo de tempo, etc.")
    model_prob: float | None = Field(None, ge=0, le=1, description="Probabilidade do modelo (in-play ou KXL)")
    market_odd: float | None = Field(None, gt=1, description="Odd capturada na Superbet para esta perna")
    expected_value: float | None = Field(None, description="EV da perna (modelo × odd − 1)")
    edge_pp: float | None = Field(None, description="Edge em pontos percentuais vs mercado")


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
    source: str = Field("extension", description="Origem: extension | manual | bolao_proposal")
    captured_at: str | None = Field(None, description="ISO timestamp de quando a aposta foi capturada")
    minute: int | None = Field(
        None,
        ge=0,
        le=120,
        description="Minuto do jogo no momento do cadastro (para guardrails P0)",
    )
    model_source: str | None = Field(
        None,
        description="Origem do modelo: inplay_market_scan | kxl_patterns",
    )
    combined_ev: float | None = Field(None, description="EV combinado (prob modelo × odd mercado − 1)")
    combined_prob: float | None = Field(None, ge=0, le=1, description="Probabilidade combinada do modelo")
    bonus_eligible: bool | None = Field(None, description="Elegível promo Super Múltipla (+5%)")
    bonus_percentage: float | None = Field(None, ge=0, description="Percentual de bônus aplicado")
    final_payout: float | None = Field(None, gt=0, description="Retorno com bônus Super Múltipla")

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


class CheckAgainstModelRequest(BaseModel):
    """Verifica se um palpite 1X2 diverge do modelo (extensão / pré-cadastro)."""

    market: str = Field(..., description="Tipo de mercado (apenas h2h suportado)")
    outcome: str = Field(..., description="Palpite: 1|X|2|home|away|draw")
    home_team: str | None = Field(None, description="Mandante (opcional se superbet_event_id)")
    away_team: str | None = Field(None, description="Visitante (opcional se superbet_event_id)")
    superbet_event_id: int | None = Field(None, description="ID Superbet para resolver times + in-play")
    phase: str = Field("friendly", description="Fase WC para o predictor")
    stake: float = Field(0, ge=0)
    odds_placed: float = Field(0, ge=0)


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
