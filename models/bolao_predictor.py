from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from config import settings
from models.baseline import predict_baseline, predict_baseline_probs
from models.league_dixon_coles import predict_league_probs
from schemas.models import BolaoFeature, BolaoLabel, GoldBolaoContext

logger = structlog.get_logger()

LABELS: tuple[BolaoLabel, ...] = ("1", "X", "2")


@dataclass
class BolaoPrediction:
    prediction: BolaoLabel
    confidence: float
    reason: str
    probabilities: dict[BolaoLabel, float]
    model_source: str


def build_match_prompt(
    home_team: str,
    away_team: str,
    competition: str,
    round_number: int,
    context_text: str,
) -> str:
    return (
        f"Você é um analista esportivo. Com base nas estatísticas e notícias abaixo, "
        f"preveja o resultado do jogo {home_team} x {away_team} "
        f"({competition}, rodada {round_number}).\n\n"
        f"{context_text}\n\n"
        f"Resposta (formato bolão - use 1=mandante, X=empate, 2=visitante):"
    )


def parse_bolao_label(text: str) -> BolaoLabel | None:
    cleaned = text.strip().upper()
    for char in cleaned:
        if char in ("1", "X", "2"):
            return char  # type: ignore[return-value]
    if "EMPATE" in cleaned:
        return "X"
    if "MANDANTE" in cleaned or "CASA" in cleaned:
        return "1"
    if "VISITANTE" in cleaned or "FORA" in cleaned:
        return "2"
    return None


def _normalize_probs(probs: dict[BolaoLabel, float]) -> dict[BolaoLabel, float]:
    total = sum(probs.values())
    if total <= 0:
        return {k: 1.0 / 3 for k in LABELS}
    return {k: v / total for k, v in probs.items()}


def _blend_probs(
    baseline: dict[BolaoLabel, float],
    lm_label: BolaoLabel,
    lm_weight: float = 0.55,
) -> dict[BolaoLabel, float]:
    blended = {k: baseline[k] * (1.0 - lm_weight) for k in LABELS}
    blended[lm_label] += lm_weight
    return _normalize_probs(blended)


def _blend_prob_dicts(
    a: dict[BolaoLabel, float],
    b: dict[BolaoLabel, float],
    b_weight: float,
) -> dict[BolaoLabel, float]:
    w = min(max(b_weight, 0.0), 1.0)
    blended = {k: a[k] * (1.0 - w) + b[k] * w for k in LABELS}
    return _normalize_probs(blended)


def _ensemble_baseline_dc(
    features: BolaoFeature,
    *,
    match_date,
) -> tuple[dict[BolaoLabel, float], str | None]:
    """Combina heurística (notícias/tabela) com Dixon-Coles de liga."""
    baseline_probs = predict_baseline_probs(features)
    if not settings.bolao_use_dixon_coles:
        return baseline_probs, None

    dc_probs = predict_league_probs(
        features.home_team,
        features.away_team,
        features.competition,
        before_date=match_date,
        is_neutral=False,
    )
    if dc_probs is None:
        return baseline_probs, None

    merged = _blend_prob_dicts(baseline_probs, dc_probs, settings.bolao_dc_weight)
    return merged, "dixon_coles"


class BolaoPredictor:
    """Previsão com LM local (se checkpoint existir) ou fallback heurístico."""

    def __init__(
        self,
        model_path: Path | None = None,
        use_lm: bool | None = None,
        max_new_tokens: int | None = None,
    ):
        self.model_path = model_path or settings.bolao_model_path
        self.use_lm = settings.bolao_use_lm if use_lm is None else use_lm
        self.max_new_tokens = max_new_tokens or settings.bolao_lm_max_tokens
        self._model = None
        self._tokenizer = None
        self._lm_ready: bool | None = None

    def _checkpoint_available(self) -> bool:
        if not self.model_path.exists():
            return False
        markers = ("config.json", "adapter_config.json", "tokenizer_config.json")
        return any((self.model_path / name).exists() for name in markers)

    def _load_lm(self) -> bool:
        if self._lm_ready is not None:
            return self._lm_ready
        if not self.use_lm or not self._checkpoint_available():
            self._lm_ready = False
            return False
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            adapter_cfg = self.model_path / "adapter_config.json"
            if adapter_cfg.exists():
                from peft import PeftModel

                import json

                base_name = json.loads(adapter_cfg.read_text(encoding="utf-8")).get(
                    "base_model_name_or_path",
                    settings.bolao_lm_base_model,
                )
                tokenizer = AutoTokenizer.from_pretrained(self.model_path, use_fast=True)
                base = AutoModelForCausalLM.from_pretrained(
                    base_name,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                )
                self._model = PeftModel.from_pretrained(base, str(self.model_path))
            else:
                tokenizer = AutoTokenizer.from_pretrained(self.model_path, use_fast=True)
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                )
            self._tokenizer = tokenizer
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            self._model.eval()
            self._lm_ready = True
            logger.info("bolao_lm_loaded", path=str(self.model_path))
        except Exception as exc:
            logger.warning("bolao_lm_load_failed", error=str(exc), path=str(self.model_path))
            self._lm_ready = False
        return self._lm_ready

    def _predict_lm(self, prompt: str) -> BolaoLabel | None:
        if not self._load_lm() or self._model is None or self._tokenizer is None:
            return None
        try:
            import torch

            inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
            device = next(self._model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                out = self._model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    pad_token_id=self._tokenizer.pad_token_id,
                )
            new_tokens = out[0, inputs["input_ids"].shape[1] :]
            text = self._tokenizer.decode(new_tokens, skip_special_tokens=True)
            return parse_bolao_label(text)
        except Exception as exc:
            logger.warning("bolao_lm_inference_failed", error=str(exc))
            return None

    def predict_from_features(self, features: BolaoFeature) -> BolaoPrediction:
        probs, dc_source = _ensemble_baseline_dc(
            features,
            match_date=features.match_date,
        )
        pred, conf, reason = predict_baseline(features)
        if dc_source:
            pred = max(probs, key=probs.get)  # type: ignore[arg-type]
            conf = float(probs[pred])
            reason = f"Dixon-Coles + baseline: {reason}"
        return BolaoPrediction(
            prediction=pred,
            confidence=min(conf, 0.92),
            reason=reason,
            probabilities=probs,
            model_source=dc_source or "baseline",
        )

    def predict(self, context: GoldBolaoContext) -> BolaoPrediction:
        probs, dc_source = _ensemble_baseline_dc(
            context.features,
            match_date=context.match_date,
        )
        pred, conf, reason = predict_baseline(context.features)
        if dc_source:
            pred = max(probs, key=probs.get)  # type: ignore[arg-type]
            conf = float(probs[pred])
            reason = f"Dixon-Coles + baseline: {reason}"

        prompt = build_match_prompt(
            context.home_team,
            context.away_team,
            context.competition,
            context.round_number,
            context.context_text,
        )
        lm_label = self._predict_lm(prompt)
        if lm_label is None:
            return BolaoPrediction(
                prediction=pred,
                confidence=min(conf, 0.92),
                reason=reason,
                probabilities=probs,
                model_source=dc_source or "baseline",
            )

        lm_probs = _blend_probs(probs, lm_label)
        prediction = max(lm_probs, key=lm_probs.get)  # type: ignore[arg-type]
        confidence = float(lm_probs[prediction])
        return BolaoPrediction(
            prediction=prediction,
            confidence=min(confidence, 0.92),
            reason=f"modelo LM ({lm_label}); {reason}",
            probabilities=lm_probs,
            model_source="lm",
        )

    def status(self) -> dict:
        return {
            "model_path": str(self.model_path),
            "checkpoint_present": self._checkpoint_available(),
            "use_lm": self.use_lm,
            "lm_loaded": self._load_lm() if self.use_lm else False,
        }


_predictor: BolaoPredictor | None = None


def get_predictor() -> BolaoPredictor:
    global _predictor
    if _predictor is None:
        _predictor = BolaoPredictor()
    return _predictor
