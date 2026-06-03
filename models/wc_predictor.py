from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from ingest.fixtures.world_cup import load_wc_fixtures
from models.wc_collaborative import CollaborativeWcModel
from models.dixon_coles_wc import DixonColesWcModel
from models.logistic_wc import WcLogisticModel
from models.poisson_wc import goal_model_factors
from pipelines.wc_baselines import (
    blend_with_baseline,
    format_baseline_context,
)
from pipelines.wc_kxl_collision import (
    collision_predict,
    collision_to_breakdown,
    format_collision_context,
)
from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_stats import build_match_features, compute_wc_h2h, format_wc_context
from schemas.models import BolaoLabel
from schemas.wc_kxl_dynamic import WcKxlMatchInput


def _apply_draw_floor(probs: dict[str, float], floor: float) -> dict[str, float]:
    if floor <= 0:
        return probs
    px = max(probs["X"], floor)
    rem = 1.0 - px
    scale = rem / max(probs["1"] + probs["2"], 1e-9)
    return {"1": probs["1"] * scale, "X": px, "2": probs["2"] * scale}


@dataclass
class WcPrediction:
    home_team: str
    away_team: str
    prediction: BolaoLabel
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    poisson_score: str
    expected_goals: str
    context: str
    h2h_summary: str
    model_breakdown: dict


def train_wc_predictor(
    fixtures_df: pd.DataFrame | None = None,
    validation_season: int = 2022,
) -> "WcPredictor":
    predictor = WcPredictor.__new__(WcPredictor)
    predictor.fixtures = fixtures_df if fixtures_df is not None else load_wc_fixtures()
    if predictor.fixtures.empty:
        raise ValueError(
            "Nenhum dado de Copa do Mundo. Execute: import-world-cup"
        )
    predictor.logistic = WcLogisticModel()
    predictor._metrics = predictor.logistic.fit(
        predictor.fixtures, holdout_season=validation_season
    )
    predictor.dixon_coles = DixonColesWcModel()
    predictor._dc_metrics = predictor.dixon_coles.fit(
        predictor.fixtures, holdout_season=validation_season
    )
    predictor.collaborative = CollaborativeWcModel(dixon_coles=predictor.dixon_coles)
    predictor.collab_metrics = predictor.collaborative.fit(
        predictor.fixtures,
        validation_season=validation_season,
        logistic_model=predictor.logistic,
    )
    return predictor


class WcPredictor:
    def __init__(self, fixtures_df: pd.DataFrame | None = None) -> None:
        trained = train_wc_predictor(fixtures_df)
        self.fixtures = trained.fixtures
        self.logistic = trained.logistic
        self._metrics = trained._metrics
        self.dixon_coles = trained.dixon_coles
        self._dc_metrics = trained._dc_metrics
        self.collaborative = trained.collaborative
        self.collab_metrics = trained.collab_metrics

    @property
    def training_metrics(self) -> dict:
        return self._metrics

    def predict(
        self,
        home_team: str,
        away_team: str,
        phase: str = "group",
        is_neutral: bool = True,
        before_date: datetime | None = None,
        kxl_match: WcKxlMatchInput | None = None,
    ) -> WcPrediction:
        cutoff = before_date or datetime.now(timezone.utc)
        features = build_match_features(
            self.fixtures,
            home_team,
            away_team,
            before_date=cutoff,
            phase=phase,
            is_neutral=is_neutral,
        )
        h2h = compute_wc_h2h(self.fixtures, home_team, away_team, before_date=cutoff)

        poisson = self.dixon_coles.predict(
            self.fixtures,
            home_team,
            away_team,
            features,
            before_date=cutoff,
        )
        logistic = self.logistic.predict_match(
            self.fixtures,
            home_team,
            away_team,
            phase=phase,
            is_neutral=is_neutral,
            before_date=cutoff,
        )

        pw = self.collaborative.dixon_coles_weight
        lw = self.collaborative.logistic_weight
        prob_home = pw * poisson.prob_home + lw * logistic.prob_home
        prob_draw = pw * poisson.prob_draw + lw * logistic.prob_draw
        prob_away = pw * poisson.prob_away + lw * logistic.prob_away

        total = prob_home + prob_draw + prob_away
        prob_home /= total
        prob_draw /= total
        prob_away /= total

        collision_out = collision_predict(home_team, away_team, kxl_match)

        hp = get_wc_hyperparams()
        prob_home, prob_draw, prob_away, baseline_out = blend_with_baseline(
            prob_home,
            prob_draw,
            prob_away,
            home_team,
            away_team,
            weight=hp.kxl_blend_weight,
            kxl_match=kxl_match,
        )

        probs = _apply_draw_floor(
            {"1": prob_home, "X": prob_draw, "2": prob_away},
            hp.draw_prob_floor,
        )
        prob_home, prob_draw, prob_away = probs["1"], probs["X"], probs["2"]
        prediction = max(probs, key=probs.get)  # type: ignore[assignment]
        confidence = probs[prediction]

        h2h_summary = (
            f"{h2h.total} jogos em Copas | "
            f"{home_team} {h2h.home_wins}V {h2h.draws}E {h2h.away_wins}D {away_team}"
        )
        if h2h.last_results:
            h2h_summary += f" | Sequência: {' '.join(h2h.last_results)}"

        factors = goal_model_factors(
            self.fixtures,
            home_team,
            away_team,
            features=features,
            before_date=cutoff,
            rho=self.dixon_coles.rho,
        )

        return WcPrediction(
            home_team=home_team,
            away_team=away_team,
            prediction=prediction,
            confidence=confidence,
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            poisson_score=poisson.most_likely_score,
            expected_goals=f"{poisson.expected_home_goals:.1f}x{poisson.expected_away_goals:.1f}",
            context=_build_context(
                features, h2h, home_team, away_team, baseline_out, collision_out
            ),
            h2h_summary=h2h_summary,
            model_breakdown={
                "dixon_coles": {
                    "1": round(poisson.prob_home, 3),
                    "X": round(poisson.prob_draw, 3),
                    "2": round(poisson.prob_away, 3),
                },
                "logistic": {
                    "1": round(logistic.prob_home, 3),
                    "X": round(logistic.prob_draw, 3),
                    "2": round(logistic.prob_away, 3),
                },
                "dixon_coles_rho": self._dc_metrics.get("rho"),
                "poisson_factors": factors.as_dict(),
                "holdout_2022_accuracy": self._metrics.get("holdout_accuracy"),
                "ensemble_weights": {
                    "dixon_coles": round(pw, 3),
                    "logistic": round(lw, 3),
                },
                "ensemble_brier": round(self.collab_metrics.brier_score, 6),
                "squad_features": True,
                "kxl_baseline": _baseline_breakdown(baseline_out),
                "kxl_collision": (
                    collision_to_breakdown(collision_out) if collision_out else None
                ),
                "kxl_dynamic": _dynamic_blocks_used(kxl_match),
            },
        )


def _build_context(features, h2h, home_team, away_team, baseline_out, collision_out):
    parts = [format_wc_context(features, h2h)]
    dna = format_baseline_context(home_team, away_team, baseline_out)
    if dna:
        parts.append(dna)
    if collision_out:
        parts.append(format_collision_context(collision_out))
    return "\n\n".join(parts)


def _dynamic_blocks_used(kxl_match: WcKxlMatchInput | None) -> dict | None:
    if kxl_match is None:
        return None
    blocks = [
        name
        for name, val in (
            ("fecl", kxl_match.fecl),
            ("feju", kxl_match.feju),
            ("fede", kxl_match.fede),
            ("fept", kxl_match.fept),
            ("feem", kxl_match.feem),
        )
        if val is not None
    ]
    return {"blocks_used": blocks, "engine": "wc_kxl_collision"} if blocks else None


def _serialize_snapshot(snap) -> dict | None:
    if snap is None:
        return None
    return {
        "attack_index": round(snap.attack_index, 4),
        "defense_index": round(snap.defense_index, 4),
        "control_index": round(snap.control_index, 4),
        "gk_index": round(snap.gk_index, 4),
        "chaos": round(snap.chaos, 4),
        "shots_per_game": round(snap.shots_per_game, 2),
        "possession_pct": round(snap.possession_pct, 2),
        "counter_attack": round(snap.counter_attack, 2),
        "inside_goal_pct": round(snap.inside_goal_pct, 2),
        "gk_inside_weakness_pct": round(snap.gk_inside_weakness_pct, 2),
    }


def _baseline_breakdown(baseline_out) -> dict | None:
    if baseline_out is None:
        return None
    m = baseline_out.matchup
    return {
        "1": round(baseline_out.prob_home, 3),
        "X": round(baseline_out.prob_draw, 3),
        "2": round(baseline_out.prob_away, 3),
        "blend_weight": get_wc_hyperparams().kxl_blend_weight,
        "sector_note": m.sector_note,
        "home_edge": m.home_edge,
        "away_edge": m.away_edge,
        "home_attack_vs_away_def": round(m.home_attack_vs_away_def, 4),
        "away_attack_vs_home_def": round(m.away_attack_vs_home_def, 4),
        "home_snapshot": _serialize_snapshot(baseline_out.home),
        "away_snapshot": _serialize_snapshot(baseline_out.away),
    }
