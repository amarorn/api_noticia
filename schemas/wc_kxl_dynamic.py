"""Entrada dinâmica KXL por partida (blocos FECL, FEJU, FEDE, FEPT, FEEM)."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class FeclAmbiente(BaseModel):
    """bloco_1_tempo_ambiente_fecl — clima e gramado (PDF)."""

    previsao_chuva_pct: float | None = Field(None, ge=0, le=100)
    chuva_mm: float | None = Field(None, ge=0, description="Compat: precipitação em mm")
    temperatura_c: float | None = None
    umidade_pct: float | None = Field(None, ge=0, le=100)
    altitude_m: float | None = Field(None, ge=0)
    estado_gramado: str | None = Field(
        None,
        description="Natural | Sintético | Ruim | Molhado (PDF)",
    )
    gramado: str | None = Field(
        None,
        description="Alias: bom | regular | molhado | ruim | sintético",
    )


class FejuArbitro(BaseModel):
    """bloco_1_arbitragem_feju — rigor arbitral."""

    nome_arbitro: str | None = None
    faltas_media: float | None = Field(None, ge=0)
    cartoes_media: float | None = Field(None, ge=0)
    indice_cartao_falta: float | None = Field(
        None,
        ge=0,
        description="Índice CF cartão/falta (PDF)",
    )
    perfil: str | None = Field(
        None,
        description="punitivista | equilibrado | pacificador",
    )


class FedeDesfalque(BaseModel):
    jogador: str
    posicao: str | None = Field(None, description="Zaga | Meio | Ataque (PDF)")
    nota_elenco: float | None = Field(None, ge=0, le=10)
    impacto_nota_elenco: float | None = Field(
        None,
        description="Impacto negativo no elenco (PDF, ex.: -0.8)",
    )
    impacto: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Peso do desfalque (0–1), compat",
    )


class FedeElenco(BaseModel):
    """bloco_2_exogenos_fede."""

    desfalques_mandante: list[FedeDesfalque] = Field(default_factory=list)
    desfalques_visitante: list[FedeDesfalque] = Field(default_factory=list)


class FeptJogador(BaseModel):
    nome: str
    posicao: str | None = None
    nota_sofascore: float | None = Field(None, ge=0, le=10)
    linha: str | None = Field(
        None,
        description="goleiro | defesa | meio | ataque",
    )


class FeptTitularesEstruturados(BaseModel):
    """Formato aninhado do PDF (mandante_titulares_notas)."""

    goleiro: dict | FeptJogador | None = None
    defensores: list[dict | FeptJogador] = Field(default_factory=list)
    meio_campistas: list[dict | FeptJogador] = Field(default_factory=list)
    atacantes: list[dict | FeptJogador] = Field(default_factory=list)
    defesa_extra: list[dict | FeptJogador] = Field(
        default_factory=list,
        description="visitante defensao_completa_array",
    )


class FeptEscalacao(BaseModel):
    """bloco_2_escalacoes_fept."""

    esquema_mandante: str | None = None
    esquema_visitante: str | None = None
    mandante_titulares_notas: FeptTitularesEstruturados | None = None
    visitante_titulares_notas: FeptTitularesEstruturados | None = None
    titulares_mandante: list[FeptJogador] = Field(default_factory=list)
    titulares_visitante: list[FeptJogador] = Field(default_factory=list)


class FeemEmocional(BaseModel):
    """fator_emocional_feem."""

    contexto_peso_caos: float | None = Field(
        None,
        ge=0,
        le=2,
        description="Escala PDF (ex.: 1.00)",
    )
    descricao_cenario: str | None = None
    peso_rivalidade: float = Field(0.0, ge=0, le=1)
    jogo_decisivo: bool = False
    contexto_caos_extra: float = Field(0.0, ge=0, le=1)


class WcKxlPartida(BaseModel):
    mandante: str | None = None
    visitante: str | None = None


class WcKxlMatchInput(BaseModel):
    """Payload opcional do dia do jogo (API dinâmica KXL)."""

    confronto_id: str | None = None
    fase: str | None = None
    partida: WcKxlPartida | None = None
    fecl: FeclAmbiente | None = None
    feju: FejuArbitro | None = None
    fede: FedeElenco | None = None
    fept: FeptEscalacao | None = None
    feem: FeemEmocional | None = None

    @model_validator(mode="after")
    def _normalize_feem(self) -> "WcKxlMatchInput":
        if self.feem and self.feem.contexto_peso_caos is not None:
            extra = max(0.0, self.feem.contexto_peso_caos - 1.0)
            if extra > self.feem.contexto_caos_extra:
                object.__setattr__(
                    self.feem,
                    "contexto_caos_extra",
                    min(1.0, extra),
                )
        return self
