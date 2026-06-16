"""Schema das transações da Superbet capturadas via CSV de carteira."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# Tipos de transação reconhecidos
TRANSACTION_TYPES = {
    "bilhete colocado",
    "bilhete confirmado",
    "bilhete cancelado",
    "valor ganhado",
    "depósito",
    "deposito",
    "saque",
    "bônus de apostas esportivas concedido",
    "bônus de apostas esportivas resgatado",
    "crédito de freespin",
    "débito de freespin",
}

# Identifica apostas in-play da Superbet
INPLAY_GAME_PATTERN = "INPLAY-SB_BR"


class UserTransactionRow(BaseModel):
    """Uma linha do CSV de transações Superbet, normalizada."""

    transaction_at: datetime = Field(..., description="Timestamp local da transação")
    transaction_type: str = Field(..., description="Tipo: bilhete colocado, valor ganhado, etc.")
    payment_method: str | None = Field(None, description="Método: pix, cartão, etc.")
    amount: float = Field(..., description="Valor movimentado em R$")
    cash_balance: float = Field(..., description="Saldo em dinheiro após a transação")
    cash_balance_prev: float = Field(..., description="Saldo em dinheiro antes")
    bonus_balance: float = Field(0.0, description="Saldo de bônus após")
    bonus_balance_prev: float = Field(0.0, description="Saldo de bônus antes")
    game_name: str = Field(..., description="Identificador do jogo/produto")
    user_id: str = Field(..., description="Usuário dono do CSV (jamarorn, etc.)")
    upload_id: str = Field(..., description="UUID da carga, para idempotência")

    @property
    def is_inplay_bet(self) -> bool:
        """Retorna True se é uma transação de aposta in-play."""
        return INPLAY_GAME_PATTERN in (self.game_name or "")

    @property
    def is_bet_placed(self) -> bool:
        return self.transaction_type == "bilhete colocado"

    @property
    def is_bet_confirmed(self) -> bool:
        return self.transaction_type == "bilhete confirmado"

    @property
    def is_bet_cancelled(self) -> bool:
        return self.transaction_type == "bilhete cancelado"

    @property
    def is_win(self) -> bool:
        return self.transaction_type == "valor ganhado" and self.amount > 0


class TransactionUploadResponse(BaseModel):
    """Resposta ao upload de CSV."""

    upload_id: str
    user_id: str
    n_rows: int
    n_inplay_bets_placed: int
    n_wins: int
    total_staked: float
    total_won: float
    pnl: float
    file_path: str
    message: str = "ok"


class WalletSummary(BaseModel):
    """KPIs agregados da carteira do usuário."""

    user_id: str
    period_start: datetime | None
    period_end: datetime | None
    n_transactions: int
    n_bets_placed: int
    n_bets_won: int
    hit_rate: float = Field(..., description="Win rate dos bilhetes confirmados")
    total_staked: float
    total_won: float
    pnl: float
    roi: float = Field(..., description="P&L / total apostado")
    total_deposits: float
    current_balance: float
    daily_pnl: list[dict] = Field(default_factory=list, description="P&L por dia")
    by_game_type: list[dict] = Field(default_factory=list, description="Breakdown por tipo")
