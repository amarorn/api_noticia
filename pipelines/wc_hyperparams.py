"""Hiperparâmetros do modelo Copa — config + overrides em data/wc/hyperparams.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import settings

HYPERPARAMS_PATH = Path("data/wc/hyperparams.json")

_active_override = None


@dataclass(frozen=True)
class WcHyperParams:
    elo_k: float = 32.0
    elo_home_adv: float = 30.0
    elo_initial: float = 1500.0
    home_adv_goals: float = 0.12
    home_adv_goals_neutral: float = 0.04
    logistic_c: float = 0.85
    logistic_class_weight: str | None = "balanced"
    logistic_max_iter: int = 3000
    ensemble_weight_steps: int = 40
    kxl_blend_weight: float = 0.20
    rho_min: float = -0.20
    rho_max: float = 0.20
    rho_step: float = 0.01
    draw_prob_floor: float = 0.18

    def home_advantage_goals(self, is_neutral: bool) -> float:
        return self.home_adv_goals_neutral if is_neutral else self.home_adv_goals


def _from_settings_defaults() -> WcHyperParams:
    return WcHyperParams(
        elo_k=getattr(settings, "wc_elo_k", 32.0),
        elo_home_adv=getattr(settings, "wc_elo_home_adv", 30.0),
        elo_initial=getattr(settings, "wc_elo_initial", 1500.0),
        home_adv_goals=getattr(settings, "wc_home_adv_goals", 0.12),
        home_adv_goals_neutral=getattr(settings, "wc_home_adv_goals_neutral", 0.04),
        logistic_c=getattr(settings, "wc_logistic_c", 0.85),
        logistic_class_weight=getattr(settings, "wc_logistic_class_weight", "balanced"),
        logistic_max_iter=getattr(settings, "wc_logistic_max_iter", 3000),
        ensemble_weight_steps=getattr(settings, "wc_ensemble_weight_steps", 40),
        kxl_blend_weight=getattr(settings, "wc_kxl_blend_weight", 0.20),
        rho_min=getattr(settings, "wc_rho_min", -0.20),
        rho_max=getattr(settings, "wc_rho_max", 0.20),
        rho_step=getattr(settings, "wc_rho_step", 0.01),
        draw_prob_floor=getattr(settings, "wc_draw_prob_floor", 0.18),
    )


def _merge_dict(base: WcHyperParams, overrides: dict[str, Any]) -> WcHyperParams:
    valid = {k: v for k, v in overrides.items() if k in base.__dataclass_fields__}
    if valid.get("logistic_class_weight") == "none":
        valid["logistic_class_weight"] = None
    return replace(base, **valid) if valid else base


@lru_cache(maxsize=1)
def load_hyperparams_file(path: Path | None = None) -> WcHyperParams | None:
    p = path or HYPERPARAMS_PATH
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    block = data.get("hyperparams", data)
    base = _from_settings_defaults()
    return _merge_dict(base, block)


def get_wc_hyperparams() -> WcHyperParams:
    if _active_override is not None:
        return _active_override
    tuned = load_hyperparams_file()
    if tuned is not None:
        return tuned
    return _from_settings_defaults()


def set_active_hyperparams(hp: WcHyperParams | None) -> None:
    global _active_override
    _active_override = hp


def save_hyperparams(hp: WcHyperParams, path: Path | None = None, meta: dict | None = None) -> Path:
    p = path or HYPERPARAMS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "hyperparams": asdict(hp),
        **(meta or {}),
    }
    if payload["hyperparams"].get("logistic_class_weight") is None:
        payload["hyperparams"]["logistic_class_weight"] = "none"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    load_hyperparams_file.cache_clear()
    return p


def clear_hyperparams_cache() -> None:
    load_hyperparams_file.cache_clear()
