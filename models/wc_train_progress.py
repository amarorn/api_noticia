from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from config import settings

TRAIN_STEPS = (
    "logistic_regression",
    "dixon_coles",
    "collaborative_ensemble",
    "draw_model",
    "persist_artifact",
)

STEP_LABELS: dict[str, str] = {
    "logistic_regression": "Regressão logística + calibração",
    "dixon_coles": "Dixon-Coles (rho)",
    "collaborative_ensemble": "Ensemble colaborativo",
    "draw_model": "Modelo de empate",
    "persist_artifact": "Salvando artefato",
}


@dataclass
class TrainProgressState:
    status: str
    step: str | None = None
    step_label: str | None = None
    step_index: int = 0
    total_steps: int = len(TRAIN_STEPS)
    detail: str | None = None
    percent: float | None = None
    started_at: str | None = None
    updated_at: str | None = None
    elapsed_sec: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    mlflow_run_id: str | None = None
    mlflow_ui_url: str | None = None


class TrainProgressReporter(Protocol):
    def start(self, fixtures: int) -> None: ...

    def step_start(self, step: str, detail: str | None = None) -> None: ...

    def step_progress(self, current: int, total: int, detail: str | None = None) -> None: ...

    def step_done(self, step: str, metrics: dict[str, Any] | None = None) -> None: ...

    def complete(self, summary: dict[str, Any]) -> None: ...

    def fail(self, error: str) -> None: ...


def progress_path() -> Path:
    return settings.wc_artifact_dir / "train_progress.json"


def read_train_progress() -> TrainProgressState | None:
    path = progress_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return TrainProgressState(**raw)
    except (json.JSONDecodeError, TypeError):
        return None


class NullTrainProgressReporter:
    def start(self, fixtures: int) -> None:
        return

    def step_start(self, step: str, detail: str | None = None) -> None:
        return

    def step_progress(self, current: int, total: int, detail: str | None = None) -> None:
        return

    def step_done(self, step: str, metrics: dict[str, Any] | None = None) -> None:
        return

    def complete(self, summary: dict[str, Any]) -> None:
        return

    def fail(self, error: str) -> None:
        return


class WcTrainProgressReporter:
    def __init__(self, *, console: bool = False) -> None:
        self.console = console and sys.stdout.isatty()
        self._started: datetime | None = None
        self._state = TrainProgressState(status="idle")
        self._last_console_pct = -1

    def _persist(self) -> None:
        self._state.updated_at = datetime.now(UTC).isoformat()
        if self._started is not None:
            self._state.elapsed_sec = round(
                (datetime.now(UTC) - self._started).total_seconds(),
                1,
            )
        path = progress_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self._state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _println(self, message: str) -> None:
        if self.console:
            print(message, flush=True)

    def start(self, fixtures: int) -> None:
        self._started = datetime.now(UTC)
        self._last_console_pct = -1
        self._state = TrainProgressState(
            status="running",
            started_at=self._started.isoformat(),
            detail=f"{fixtures} jogos no lake",
        )
        self._persist()
        self._println(f"Treino WC iniciado ({fixtures} jogos)")

    def step_start(self, step: str, detail: str | None = None) -> None:
        idx = TRAIN_STEPS.index(step) if step in TRAIN_STEPS else 0
        label = STEP_LABELS.get(step, step)
        self._state.step = step
        self._state.step_label = label
        self._state.step_index = idx + 1
        self._state.detail = detail
        self._state.percent = None
        self._last_console_pct = -1
        self._persist()
        self._println(f"[{idx + 1}/{len(TRAIN_STEPS)}] {label}…")

    def step_progress(self, current: int, total: int, detail: str | None = None) -> None:
        pct = round((current / total) * 100, 1) if total else 0.0
        self._state.percent = pct
        self._state.detail = detail or f"{current}/{total}"
        self._persist()
        if not self.console or total <= 0:
            return
        bucket = int(pct // 5) * 5
        if bucket != self._last_console_pct or current >= total:
            self._last_console_pct = bucket
            label = self._state.step_label or self._state.step or "progresso"
            self._println(f"  {label}: {current}/{total} ({pct:.0f}%)")

    def step_done(self, step: str, metrics: dict[str, Any] | None = None) -> None:
        if metrics:
            self._state.metrics.update(metrics)
        self._state.percent = 100.0
        self._persist()
        label = STEP_LABELS.get(step, step)
        self._println(f"  {label}: concluído")

    def complete(self, summary: dict[str, Any]) -> None:
        self._state.status = "completed"
        self._state.percent = 100.0
        self._state.detail = "Treino finalizado"
        self._state.metrics.update(summary)
        self._persist()
        elapsed = self._state.elapsed_sec
        elapsed_txt = f" em {elapsed:.0f}s" if elapsed is not None else ""
        self._println(f"Treino WC concluído{elapsed_txt}")

    def fail(self, error: str) -> None:
        self._state.status = "failed"
        self._state.error = error
        self._persist()
        self._println(f"Treino WC falhou: {error}")
