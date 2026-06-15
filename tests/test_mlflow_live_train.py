"""Testes de logging MLflow ao vivo durante treino WC."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from models.wc_train_progress import NullTrainProgressReporter, WcTrainProgressReporter
from pipelines.mlflow_live_train import MlflowTrainProgressBridge, MlflowWcTrainSession, attach_mlflow_live


def test_attach_mlflow_wraps_reporter():
    inner = NullTrainProgressReporter()
    wrapped, session = attach_mlflow_live(inner)
    assert isinstance(wrapped, MlflowTrainProgressBridge)
    assert isinstance(session, MlflowWcTrainSession)


def test_live_session_logs_progress_during_steps():
    mock_run = MagicMock()
    mock_run.info.run_id = "live-run-1"
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_run

    session = MlflowWcTrainSession()
    session._mlflow_available = True

    with (
        patch("mlflow.set_tracking_uri"),
        patch("mlflow.set_experiment"),
        patch("mlflow.start_run", return_value=mock_cm) as start_run,
        patch("mlflow.set_tag") as set_tag,
        patch("mlflow.log_param"),
        patch("mlflow.log_metric") as log_metric,
    ):
        run_id = session.start(9181)
        session.on_step_start("dixon_coles", 2)
        session.on_step_progress(45.0)
        session.on_step_progress(47.0)  # mesmo bucket — não duplica
        session.on_step_done("dixon_coles", {"rho": -0.05})

    assert run_id == "live-run-1"
    start_run.assert_called_once()
    set_tag.assert_any_call("run_kind", "wc_train_live")
    set_tag.assert_any_call("current_step", "dixon_coles")
    progress_calls = [c.args[1] for c in log_metric.call_args_list if c.args[0] == "train_progress_pct"]
    assert 45.0 in progress_calls
    assert any(c.kwargs.get("step") is not None for c in log_metric.call_args_list if c.args[0] == "train_progress_pct")
    logged = {c.args[0]: c.args[1] for c in log_metric.call_args_list}
    assert logged["dixon_coles_rho"] == -0.05


def test_bridge_persists_mlflow_run_id_in_progress(tmp_path, monkeypatch):
    monkeypatch.setattr("models.wc_train_progress.settings.wc_artifact_dir", tmp_path)

    inner = WcTrainProgressReporter(console=False)
    session = MlflowWcTrainSession()
    session._mlflow_available = True
    bridge = MlflowTrainProgressBridge(inner, session)

    mock_run = MagicMock()
    mock_run.info.run_id = "bridge-run"
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_run

    with (
        patch("mlflow.set_tracking_uri"),
        patch("mlflow.set_experiment"),
        patch("mlflow.start_run", return_value=mock_cm),
        patch("mlflow.set_tag"),
        patch("mlflow.log_param"),
        patch("mlflow.log_metric"),
    ):
        bridge.start(100)

    state = inner._state
    assert state.mlflow_run_id == "bridge-run"
    assert state.mlflow_ui_url == "http://127.0.0.1:5001"
