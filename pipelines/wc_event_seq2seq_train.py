"""Pipeline de treino do modelo seq2seq de eventos in-play.

Constrói sequências de eventos a partir de match_states.parquet + Sofascore bronze,
associa labels de "próximo gol" do nextgoal_labels.parquet e treina o LSTM.

CLI: train-event-seq2seq [--epochs N] [--lr float]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings
from models.wc_event_seq2seq import EventSeq2Seq, encode_events, SEQ_FEATURES
from models.wc_live_momentum import GameEvent
from pipelines.inplay_match_states import MATCH_STATES_PATH

logger = logging.getLogger(__name__)


def _load_sofascore_events(event_id: int) -> list[GameEvent]:
    """Carrega eventos Sofascore do bronze para um event_id."""
    from ingest.sofascore.live_events import _parse_incidents

    ss_id_path = settings.bronze_path / "sofascore" / "live"
    if not ss_id_path.exists():
        return []

    # Tentar resolver ID Sofascore pelo nome das pastas
    for folder in ss_id_path.iterdir():
        latest = folder / "latest.json"
        if latest.exists():
            try:
                data = json.loads(latest.read_text())
                if str(data.get("superbet_event_id") or "") == str(event_id):
                    incidents = data.get("incidents", [])
                    return _parse_incidents(incidents)
            except Exception:
                continue
    return []


def build_seq2seq_dataset(
    states_path: Path | None = None,
    nextgoal_path: Path | None = None,
) -> tuple[list[np.ndarray], np.ndarray]:
    """Constrói dataset de sequências para treino do seq2seq.

    Estratégia:
    1. Para cada (event_id, tick) no nextgoal_labels.parquet, temos o label (0/1/2).
    2. Carrega eventos Sofascore do bronze para o event_id.
    3. Encoda a sequência de eventos ANTES do minuto do tick.
    4. Usa o label de nextgoal como target.

    Returns:
        (X_seqs, y) onde X_seqs é lista de arrays (T_i, SEQ_FEATURES)
        e y é array de labels int64.
    """
    from pipelines.wc_inplay_nextgoal_labels import NEXTGOAL_DATASET_PATH

    ng_path = nextgoal_path or NEXTGOAL_DATASET_PATH
    if not ng_path.exists():
        logger.warning("nextgoal_labels não encontrado: %s", ng_path)
        return [], np.array([])

    ng_df = pd.read_parquet(ng_path)
    if ng_df.empty or "label" not in ng_df.columns:
        return [], np.array([])

    X_seqs: list[np.ndarray] = []
    y_labels: list[int] = []

    # Cache de eventos por event_id para não recarregar
    events_cache: dict[int, list[GameEvent]] = {}

    for event_id in ng_df["event_id"].unique():
        eid = int(event_id)
        if eid not in events_cache:
            events_cache[eid] = _load_sofascore_events(eid)

        events = events_cache[eid]
        ticks = ng_df[ng_df["event_id"] == eid]

        for _, tick in ticks.iterrows():
            minute = float(tick["minute"])
            label = int(tick["label"])

            X = encode_events(events, minute)
            X_seqs.append(X)
            y_labels.append(label)

    y = np.array(y_labels, dtype=np.int64)
    logger.info("seq2seq_dataset", n_sequences=len(X_seqs),
                label_0=(y == 0).sum(), label_1=(y == 1).sum(), label_2=(y == 2).sum())
    return X_seqs, y


def train_seq2seq(
    n_epochs: int = 50,
    lr: float = 1e-3,
    seed: int = 42,
    states_path: Path | None = None,
) -> dict[str, Any]:
    """Treina o EventSeq2Seq e salva o artefato.

    Returns:
        Dict com métricas e path do artefato.
    """
    X_seqs, y = build_seq2seq_dataset(states_path=states_path)

    if len(X_seqs) < 50:
        return {
            "error": f"Sequências insuficientes: {len(X_seqs)} < 50. "
                     "Execute build-nextgoal-labels primeiro."
        }

    model = EventSeq2Seq(window_minutes=10)
    try:
        metrics = model.fit_torch(X_seqs, y, n_epochs=n_epochs, lr=lr, seed=seed)
        path = model.save()
        return {**metrics, "artifact_path": str(path), "backend": "torch"}
    except RuntimeError as exc:
        # PyTorch não disponível: salvar modelo sem treino (numpy inference)
        logger.warning("pytorch_indisponivel: %s", exc)
        path = model.save()
        return {
            "warning": "PyTorch não disponível — modelo salvo sem treino. "
                       "Instale torch para treino completo.",
            "artifact_path": str(path),
            "n_sequences": len(X_seqs),
            "backend": "numpy",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Treina seq2seq de eventos in-play")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = train_seq2seq(n_epochs=args.epochs, lr=args.lr)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
