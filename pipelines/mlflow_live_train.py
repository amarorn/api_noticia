"""Logging MLflow em tempo real durante o treino WC."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from config import settings
from models.wc_train_progress import TrainProgressReporter, WcTrainProgressReporter


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _log_step_metrics(step: str, metrics: dict[str, Any] | None) -> None:
    if not metrics:
        return
    import mlflow

    for key, value in metrics.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                fv = _safe_float(sub_value)
                if fv is not None:
                    mlflow.log_metric(f"{step}_{key}_{sub_key}", fv)
            continue
        fv = _safe_float(value)
        if fv is not None:
            mlflow.log_metric(f"{step}_{key}", fv)


class MlflowWcTrainSession:
    """Mantém um run MLflow aberto durante todo o treino."""

    def __init__(self) -> None:
        self._cm = None
        self._run_id: str | None = None
        self._last_progress_bucket = -1
        self._progress_step = 0
        self._active = False
        try:
            import mlflow  # noqa: F401

            self._mlflow_available = True
        except ImportError:
            self._mlflow_available = False

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def active(self) -> bool:
        return self._active

    def start(self, fixtures: int) -> str | None:
        if not self._mlflow_available:
            return None
        import mlflow

        from pipelines.mlflow_tracking import setup_mlflow

        setup_mlflow(settings.mlflow_experiment_wc_train)
        run_name = datetime.now(UTC).strftime("wc-train-%Y%m%dT%H%M%SZ")
        self._cm = mlflow.start_run(run_name=run_name)
        run = self._cm.__enter__()
        self._run_id = run.info.run_id
        self._active = True
        mlflow.set_tag("run_kind", "wc_train_live")
        mlflow.set_tag("status", "running")
        mlflow.log_param("fixture_rows", fixtures)
        self._progress_step = 0
        mlflow.log_metric("train_progress_pct", 0.0, step=self._progress_step)
        mlflow.log_metric("train_step_index", 0.0, step=0)
        return self._run_id

    def on_step_start(self, step: str, step_index: int) -> None:
        if not self._active:
            return
        import mlflow

        mlflow.set_tag("current_step", step)
        mlflow.log_metric("train_step_index", float(step_index), step=step_index)
        self._last_progress_bucket = -1
        self._progress_step = step_index * 100

    def on_step_progress(self, percent: float | None) -> None:
        if not self._active or percent is None:
            return
        bucket = int(percent // 5) * 5
        if bucket == self._last_progress_bucket and percent < 100:
            return
        self._last_progress_bucket = bucket
        import mlflow

        self._progress_step += 1
        mlflow.log_metric("train_progress_pct", float(percent), step=self._progress_step)

    def on_step_done(self, step: str, metrics: dict[str, Any] | None) -> None:
        if not self._active:
            return
        import mlflow

        _log_step_metrics(step, metrics)
        self._progress_step += 1
        mlflow.log_metric("train_progress_pct", 100.0, step=self._progress_step)

    def on_complete(self, summary: dict[str, Any]) -> None:
        if not self._active:
            return
        import mlflow

        for key, value in summary.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    fv = _safe_float(sub_value)
                    if fv is not None:
                        mlflow.log_metric(f"final_{key}_{sub_key}", fv)
                continue
            fv = _safe_float(value)
            if fv is not None:
                mlflow.log_metric(f"final_{key}", fv)

    def finalize(
        self,
        manifest: dict,
        *,
        elapsed_sec: float | None = None,
        log_artifacts: bool = True,
    ) -> str | None:
        if not self._active:
            return self._run_id
        import mlflow

        from pipelines.mlflow_tracking import apply_manifest_to_run

        apply_manifest_to_run(
            manifest,
            elapsed_sec=elapsed_sec,
            log_artifacts=log_artifacts,
        )
        mlflow.set_tag("status", "completed")
        self._close()
        return self._run_id

    def fail(self, error: str) -> None:
        if not self._active:
            return
        import mlflow

        mlflow.set_tag("status", "failed")
        mlflow.log_param("error", error[:500])
        self._close()

    def _close(self) -> None:
        if self._cm is not None:
            self._cm.__exit__(None, None, None)
        self._cm = None
        self._active = False


class MlflowTrainProgressBridge:
    """Encadeia reporter local + sessão MLflow ao vivo."""

    def __init__(self, inner: TrainProgressReporter, session: MlflowWcTrainSession) -> None:
        self._inner = inner
        self._session = session

    def _sync_mlflow_meta(self, run_id: str | None) -> None:
        if not run_id or not isinstance(self._inner, WcTrainProgressReporter):
            return
        self._inner._state.mlflow_run_id = run_id
        self._inner._state.mlflow_ui_url = "http://127.0.0.1:5001"
        self._inner._persist()

    def start(self, fixtures: int) -> None:
        self._inner.start(fixtures)
        run_id = self._session.start(fixtures)
        self._sync_mlflow_meta(run_id)

    def step_start(self, step: str, detail: str | None = None) -> None:
        self._inner.step_start(step, detail)
        if isinstance(self._inner, WcTrainProgressReporter):
            self._session.on_step_start(step, self._inner._state.step_index)

    def step_progress(self, current: int, total: int, detail: str | None = None) -> None:
        self._inner.step_progress(current, total, detail)
        if isinstance(self._inner, WcTrainProgressReporter):
            self._session.on_step_progress(self._inner._state.percent)

    def step_done(self, step: str, metrics: dict[str, Any] | None = None) -> None:
        self._inner.step_done(step, metrics)
        self._session.on_step_done(step, metrics)

    def complete(self, summary: dict[str, Any]) -> None:
        self._inner.complete(summary)
        self._session.on_complete(summary)

    def fail(self, error: str) -> None:
        self._inner.fail(error)
        self._session.fail(error)


def attach_mlflow_live(
    reporter: TrainProgressReporter,
) -> tuple[TrainProgressReporter, MlflowWcTrainSession]:
    session = MlflowWcTrainSession()
    if not session._mlflow_available:
        return reporter, session
    return MlflowTrainProgressBridge(reporter, session), session
