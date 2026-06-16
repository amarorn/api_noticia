"""Handicap vs placar ao vivo — gates e contexto para recomendações in-play."""
from __future__ import annotations

import re
from dataclasses import dataclass

_HCAP_MARKET_RE = re.compile(r"^(ft|1h|2h)_(hcap|ah)_(home|away)_(.+)$")
_HCAP_ANY_RE = _HCAP_MARKET_RE


def handicap_line_from_key(line_key: str) -> float | None:
    """Converte chave estável (-0.5 → m0_5) em linha numérica."""
    if line_key == "0":
        return 0.0
    if line_key.startswith("m"):
        try:
            return -float(line_key[1:].replace("_", "."))
        except ValueError:
            return None
    if line_key.startswith("p"):
        try:
            return float(line_key[1:].replace("_", "."))
        except ValueError:
            return None
    return None


def parse_period_handicap_market(market: str) -> tuple[str, str, float] | None:
    """Retorna (periodo, lado, linha) para mercados ft/1h/2h_hcap_* (europeu)."""
    match = _HCAP_MARKET_RE.match(market)
    if not match:
        return None
    if match.group(2) == "ah":
        return None
    line = handicap_line_from_key(match.group(4))
    if line is None:
        return None
    return match.group(1), match.group(3), line


@dataclass(frozen=True)
class HandicapScoreAssessment:
    """Avaliação de uma linha de handicap dado o placar atual."""

    status: str
    block_suggestion: bool
    reason: str
    score_hint: str


def parse_any_handicap_market(market: str) -> tuple[str, str, float, bool] | None:
    """Retorna (periodo, lado, linha, asiatico) para ft/1h/2h hcap ou ah."""
    match = _HCAP_ANY_RE.match(market)
    if not match:
        return None
    line = handicap_line_from_key(match.group(4))
    if line is None:
        return None
    is_asian = match.group(2) == "ah"
    return match.group(1), match.group(3), line, is_asian


def _period_goals(
    period: str,
    side: str,
    *,
    home_score: int,
    away_score: int,
    minute: int,
    ht_home: int | None,
    ht_away: int | None,
) -> tuple[int, int, bool]:
    """Gols do lado apostado vs adversário no período; period_closed se já encerrou."""
    if period == "ft":
        side_g = home_score if side == "home" else away_score
        opp_g = away_score if side == "home" else home_score
        return side_g, opp_g, False

    if period == "1h":
        if minute <= 45:
            side_g = home_score if side == "home" else away_score
            opp_g = away_score if side == "home" else home_score
            return side_g, opp_g, False
        ht_h = ht_home if ht_home is not None else home_score
        ht_a = ht_away if ht_away is not None else away_score
        side_g = ht_h if side == "home" else ht_a
        opp_g = ht_a if side == "home" else ht_h
        return side_g, opp_g, True

    # 2º tempo
    ht_h = ht_home if ht_home is not None else 0
    ht_a = ht_away if ht_away is not None else 0
    sh_h = max(0, home_score - ht_h)
    sh_a = max(0, away_score - ht_a)
    side_g = sh_h if side == "home" else sh_a
    opp_g = sh_a if side == "home" else sh_h
    closed = minute >= 90
    return side_g, opp_g, closed


def _european_covers(side_g: int, opp_g: int, line: float, side: str) -> bool:
    """Cover do handicap europeu no placar do período."""
    margin = float(side_g - opp_g)
    if side == "home":
        return margin + line > 0
    return margin - line > 0


def _asian_covers_now(side_g: int, opp_g: int, line: float, side: str) -> bool:
    """Cover asiático no placar parcial (sem push em linha inteira — conservador)."""
    margin = float(side_g - opp_g)
    adj = margin + line if side == "home" else margin - line
    if abs(line - round(line)) < 1e-9 and abs(adj) < 1e-9:
        return False
    return adj > 0


def _minimum_outcome_label(
    side: str,
    line: float,
    *,
    home_score: int,
    away_score: int,
    home_team: str,
    away_team: str,
) -> str:
    """Descreve o placar final mínimo para cover (FT, europeu)."""
    team = home_team if side == "home" else away_team
    h, a = home_score, away_score

    if line <= -0.5:
        if side == "home":
            need = a - h + 1
            if need <= 0:
                return f"{team} já cobre com vitória"
            return f"{team} precisa vencer (ex.: {a}×{h + need})"
        need = h - a + 1
        if need <= 0:
            return f"{team} já cobre com vitória"
        return f"{team} precisa vencer (ex.: {h}×{a + need})"

    if line >= 0.5:
        return f"{team} cobre com empate ou vitória (não perder por {int(line) + 1}+)"

    # linha 0
    if side == "home":
        return f"{team} precisa vencer (empate anula handicap 0)"
    return f"{team} precisa vencer (empate anula handicap 0)"


def assess_handicap_vs_live_score(
    market: str,
    *,
    home_score: int,
    away_score: int,
    minute: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    home_team: str = "Casa",
    away_team: str = "Fora",
    comeback_deficit_threshold: int = 3,
) -> HandicapScoreAssessment | None:
    """Cruza linha de handicap com placar ao vivo para gates e rótulos."""
    parsed = parse_any_handicap_market(market)
    if not parsed:
        european = parse_period_handicap_market(market)
        if not european:
            return None
        period, side, line = european
        is_asian = False
    else:
        period, side, line, is_asian = parsed

    side_g, opp_g, period_closed = _period_goals(
        period,
        side,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        ht_home=ht_home,
        ht_away=ht_away,
    )

    if is_asian:
        covers = _asian_covers_now(side_g, opp_g, line, side)
    else:
        covers = _european_covers(side_g, opp_g, line, side)

    score_str = f"{home_score}×{away_score}"
    team = home_team if side == "home" else away_team
    line_label = f"{line:+.1f}".replace("+", "+")
    hint = _minimum_outcome_label(
        side,
        line,
        home_score=home_score,
        away_score=away_score,
        home_team=home_team,
        away_team=away_team,
    )

    if period_closed:
        if covers:
            return HandicapScoreAssessment(
                status="settled_won",
                block_suggestion=True,
                reason=f"Período encerrado; {team} handicap {line_label} já ganhou.",
                score_hint=hint,
            )
        return HandicapScoreAssessment(
            status="settled_lost",
            block_suggestion=True,
            reason=f"Período encerrado; {team} handicap {line_label} já perdeu ({score_str}).",
            score_hint=hint,
        )

    if covers:
        return HandicapScoreAssessment(
            status="on_track",
            block_suggestion=False,
            reason=f"Placar {score_str} favorece {team} handicap {line_label}.",
            score_hint=hint,
        )

    deficit = opp_g - side_g
    needs_win = line <= -0.5 or (line == 0.0 and not is_asian)

    if needs_win and deficit > 0:
        if deficit >= comeback_deficit_threshold:
            return HandicapScoreAssessment(
                status="needs_comeback",
                block_suggestion=True,
                reason=(
                    f"Placar {score_str}; {team} handicap {line_label} exige virada de "
                    f"{deficit}+ gols — improvável."
                ),
                score_hint=hint,
            )
        return HandicapScoreAssessment(
            status="needs_win",
            block_suggestion=False,
            reason=f"Placar {score_str}; {hint}.",
            score_hint=hint,
        )

    return HandicapScoreAssessment(
        status="needs_goals",
        block_suggestion=False,
        reason=f"Placar {score_str}; {hint}.",
        score_hint=hint,
    )


def handicap_blocked_by_score(
    market: str,
    *,
    home_score: int,
    away_score: int,
    minute: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    home_team: str = "Casa",
    away_team: str = "Fora",
) -> tuple[bool, str]:
    """True se o handicap não deve ser sugerido dado o placar."""
    assessment = assess_handicap_vs_live_score(
        market,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        ht_home=ht_home,
        ht_away=ht_away,
        home_team=home_team,
        away_team=away_team,
    )
    if assessment is None:
        return False, ""
    return assessment.block_suggestion, assessment.reason


def mirror_line_key(line_key: str) -> str:
    """Espelho Superbet: m0_5 ↔ p0_5."""
    if line_key == "0":
        return "0"
    if line_key.startswith("m"):
        return f"p{line_key[1:]}"
    if line_key.startswith("p"):
        return f"m{line_key[1:]}"
    return line_key


def paired_handicap_line_keys(line_key: str) -> tuple[str, str]:
    """Retorna (chave_mandante, chave_visitante) no mercado de 2 vias."""
    val = handicap_line_from_key(line_key)
    if val is None or val == 0:
        return line_key, line_key
    if val < 0:
        return line_key, mirror_line_key(line_key)
    return mirror_line_key(line_key), line_key


def superbet_handicap_line_label(side: str, line_key: str) -> str:
    """Rótulo da linha como aparece no botão Superbet daquele time."""
    home_key, away_key = paired_handicap_line_keys(line_key)
    key = home_key if side == "home" else away_key
    val = handicap_line_from_key(key)
    if val is None:
        return line_key
    return f"{val:+.1f}".replace("+", "+")


def superbet_handicap_help(
    home_team: str,
    away_team: str,
    side: str,
    line_key: str,
) -> str:
    """Explica diferença entre botão Superbet (+0.5) e vitória pura (−0.5)."""
    btn = superbet_handicap_line_label(side, line_key)
    home_key, away_key = paired_handicap_line_keys(line_key)
    neg_val = handicap_line_from_key(home_key if home_key.startswith("m") else away_key)
    team = home_team if side == "home" else away_team
    if (
        side == "away"
        and home_key != away_key
        and neg_val is not None
        and neg_val <= -0.5
    ):
        return (
            f"Botão Superbet: {team} {btn}. "
            f"Vitória pura ({team} {neg_val:+.1f}) ≠ botão {btn} — empate também cobre {btn}."
        )
    return f"Botão Superbet: {team} {btn}"


def format_handicap_label_with_score(
    base_label: str,
    assessment: HandicapScoreAssessment | None,
) -> str:
    """Anexa contexto de placar ao rótulo da sugestão."""
    if assessment is None or not assessment.score_hint:
        return base_label
    if assessment.status == "on_track":
        return f"{base_label} · no caminho"
    return f"{base_label} · {assessment.score_hint}"
