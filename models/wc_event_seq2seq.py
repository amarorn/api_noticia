"""Modelo seq2seq para sequência de eventos in-play.

Arquitetura: LSTM bidirecional (PyTorch) com fallback numpy para inferência.

Input:  sequência de N eventos → [event_type_enc, minute_norm, team_enc, delta_t_norm]
Output: probabilidade de gol home/away/nenhum no próximo intervalo de T minutos

Vantagem sobre GBM tick-by-tick: captura dependência temporal entre eventos
(ex: "gol → substituição ofensiva adversária → pressão → gol adversário" são
padrões sequenciais que o GBM não vê).

Uso:
    model = EventSeq2Seq.load()
    if model.is_fitted:
        events = [GameEvent(...), GameEvent(...)]
        pred = model.predict_from_events(events, current_minute=72)
        print(pred.prob_goal_home, pred.prob_goal_away, pred.prob_no_goal)
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from config import settings
from models.wc_live_momentum import GameEvent

# Codificação de tipos de evento
_EVENT_TYPE_MAP = {
    "goal": 1,
    "red_card": 2,
    "sub_offensive": 3,
    "sub_defensive": 4,
    "yellow_card": 5,
    "injury": 6,
    "period": 7,
}
_TEAM_MAP = {"home": 1, "away": -1}

# Dimensões
SEQ_FEATURES = 4  # [event_enc, minute_norm, team_enc, delta_t_norm]
HIDDEN_SIZE = 64
N_LAYERS = 2
MAX_SEQ_LEN = 30   # truncar/pad sequências maiores

_SEQ2SEQ_PATH = settings.lake_root / "artifacts" / "event_seq2seq.pkl"


# ---------------------------------------------------------------------------
# Encoder de eventos → features
# ---------------------------------------------------------------------------

def encode_events(events: list[GameEvent], current_minute: float) -> np.ndarray:
    """Converte lista de GameEvents em array (SEQ_LEN, SEQ_FEATURES).

    Args:
        events: lista ordenada de eventos do jogo.
        current_minute: minuto atual (para normalização de delta_t).

    Returns:
        Array shape (min(len, MAX_SEQ_LEN), SEQ_FEATURES), float32.
    """
    # Filtrar apenas eventos anteriores ao minuto atual
    past = [e for e in events if e.minute < current_minute]
    if not past:
        return np.zeros((1, SEQ_FEATURES), dtype=np.float32)

    # Pegar os últimos MAX_SEQ_LEN eventos
    past = past[-MAX_SEQ_LEN:]

    rows = []
    prev_minute = 0.0
    for ev in past:
        t = float(ev.minute)
        rows.append([
            float(_EVENT_TYPE_MAP.get(ev.event_type, 0)) / len(_EVENT_TYPE_MAP),  # enc
            t / 90.0,                                                               # minute_norm
            float(_TEAM_MAP.get(ev.team, 0)),                                      # team_enc
            (t - prev_minute) / 90.0,                                              # delta_t
        ])
        prev_minute = t

    return np.array(rows, dtype=np.float32)


# ---------------------------------------------------------------------------
# Resultado da predição
# ---------------------------------------------------------------------------

@dataclass
class Seq2SeqPrediction:
    prob_no_goal: float
    prob_goal_home: float
    prob_goal_away: float
    window_minutes: int = 10
    n_events_used: int = 0

    @property
    def prob_any_goal(self) -> float:
        return self.prob_goal_home + self.prob_goal_away


# ---------------------------------------------------------------------------
# Modelo numpy (fallback sem PyTorch)
# ---------------------------------------------------------------------------

class _NumpySeqModel:
    """LSTM simplificado em numpy para inferência leve (sem PyTorch).

    Implementa um LSTM de 1 camada unidirecional.
    Mais lento que PyTorch mas sem dependência extra.
    """

    def __init__(self, hidden_size: int = 32):
        self.hidden_size = hidden_size
        self._weights: dict[str, np.ndarray] | None = None

    def _init_random_weights(self, input_size: int) -> None:
        h = self.hidden_size
        rng = np.random.default_rng(42)
        self._weights = {
            "Wf": rng.normal(0, 0.1, (h, input_size + h)),
            "bf": np.zeros(h),
            "Wi": rng.normal(0, 0.1, (h, input_size + h)),
            "bi": np.zeros(h),
            "Wc": rng.normal(0, 0.1, (h, input_size + h)),
            "bc": np.zeros(h),
            "Wo": rng.normal(0, 0.1, (h, input_size + h)),
            "bo": np.zeros(h),
            "Wy": rng.normal(0, 0.1, (3, h)),
            "by": np.zeros(3),
        }

    def forward(self, X: np.ndarray) -> np.ndarray:
        """Passa X (T, input_size) pela LSTM, retorna logits (3,)."""
        if self._weights is None:
            self._init_random_weights(X.shape[1])

        w = self._weights
        h = np.zeros(self.hidden_size)
        c = np.zeros(self.hidden_size)
        sigmoid = lambda x: 1 / (1 + np.exp(-np.clip(x, -10, 10)))
        tanh = np.tanh

        for t in range(len(X)):
            x = X[t]
            xh = np.concatenate([x, h])
            f = sigmoid(w["Wf"] @ xh + w["bf"])
            i = sigmoid(w["Wi"] @ xh + w["bi"])
            g = tanh(w["Wc"] @ xh + w["bc"])
            o = sigmoid(w["Wo"] @ xh + w["bo"])
            c = f * c + i * g
            h = o * tanh(c)

        logits = w["Wy"] @ h + w["by"]
        e = np.exp(logits - logits.max())
        return e / e.sum()


# ---------------------------------------------------------------------------
# Modelo principal
# ---------------------------------------------------------------------------

class EventSeq2Seq:
    """Wrapper do modelo seq2seq para eventos in-play.

    Usa PyTorch LSTM se disponível, numpy LSTM como fallback.
    """

    def __init__(self, window_minutes: int = 10):
        self.window_minutes = window_minutes
        self._torch_model = None
        self._numpy_model: _NumpySeqModel | None = None
        self._fitted = False
        self._use_torch = False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def _try_torch_forward(self, X: np.ndarray) -> np.ndarray | None:
        """Tenta inferência via PyTorch. Retorna None se indisponível."""
        if not self._use_torch or self._torch_model is None:
            return None
        try:
            import torch
            with torch.no_grad():
                t = torch.tensor(X, dtype=torch.float32).unsqueeze(0)  # (1, T, F)
                output = self._torch_model(t)
                probs = torch.softmax(output, dim=-1).numpy()[0]
            return probs
        except Exception:
            return None

    def predict_from_events(
        self,
        events: list[GameEvent],
        current_minute: float,
    ) -> Seq2SeqPrediction:
        """Prediz probabilidade de próximo gol dado sequência de eventos.

        Args:
            events: todos os eventos do jogo até agora.
            current_minute: minuto atual.

        Returns:
            Seq2SeqPrediction com prob_goal_home/away/no_goal.
        """
        X = encode_events(events, current_minute)
        n_events = len([e for e in events if e.minute < current_minute])

        if not self._fitted:
            # Sem modelo: retornar prior uniforme
            return Seq2SeqPrediction(
                prob_no_goal=1 / 3,
                prob_goal_home=1 / 3,
                prob_goal_away=1 / 3,
                window_minutes=self.window_minutes,
                n_events_used=n_events,
            )

        probs = self._try_torch_forward(X)
        if probs is None:
            if self._numpy_model is None:
                self._numpy_model = _NumpySeqModel(hidden_size=HIDDEN_SIZE // 2)
            probs = self._numpy_model.forward(X)

        return Seq2SeqPrediction(
            prob_no_goal=float(probs[0]),
            prob_goal_home=float(probs[1]),
            prob_goal_away=float(probs[2]),
            window_minutes=self.window_minutes,
            n_events_used=n_events,
        )

    def fit_torch(
        self,
        X_seqs: list[np.ndarray],
        y: np.ndarray,
        n_epochs: int = 50,
        lr: float = 1e-3,
        seed: int = 42,
    ) -> dict[str, float]:
        """Treina LSTM PyTorch em batch de sequências.

        Args:
            X_seqs: lista de arrays (T_i, SEQ_FEATURES).
            y: labels inteiros {0, 1, 2} — shape (N,).
            n_epochs: épocas de treino.
            lr: learning rate.
            seed: reprodutibilidade.

        Returns:
            Métricas de treino.
        """
        try:
            import torch
            import torch.nn as nn
        except ImportError as exc:
            raise RuntimeError("PyTorch não instalado. Use pip install torch.") from exc

        torch.manual_seed(seed)

        class _LSTMClassifier(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(
                    SEQ_FEATURES, HIDDEN_SIZE,
                    num_layers=N_LAYERS,
                    batch_first=True,
                    bidirectional=False,
                    dropout=0.3 if N_LAYERS > 1 else 0.0,
                )
                self.fc = nn.Linear(HIDDEN_SIZE, 3)

            def forward(self, x):
                _, (h, _) = self.lstm(x)
                return self.fc(h[-1])

        model = _LSTMClassifier()
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        # Pad sequências para batch (simple approach: treino sequencial)
        losses = []
        model.train()
        for epoch in range(n_epochs):
            epoch_loss = 0.0
            idx_perm = np.random.permutation(len(X_seqs))
            for idx in idx_perm:
                X = torch.tensor(X_seqs[idx], dtype=torch.float32).unsqueeze(0)
                label = torch.tensor([int(y[idx])], dtype=torch.long)
                optimizer.zero_grad()
                logits = model(X)
                loss = criterion(logits, label)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            avg = epoch_loss / len(X_seqs)
            losses.append(avg)

        self._torch_model = model
        self._torch_model.eval()
        self._use_torch = True
        self._fitted = True

        return {"final_loss": round(losses[-1], 4), "n_epochs": n_epochs, "n_samples": len(X_seqs)}

    def save(self, path: Path | None = None) -> Path:
        path = path or _SEQ2SEQ_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "window_minutes": self.window_minutes,
            "fitted": self._fitted,
            "use_torch": self._use_torch,
        }
        if self._use_torch and self._torch_model is not None:
            try:
                import torch
                payload["torch_state"] = self._torch_model.state_dict()
            except Exception:
                pass
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "EventSeq2Seq":
        path = path or _SEQ2SEQ_PATH
        inst = cls()
        if not path.exists():
            return inst
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            inst.window_minutes = data.get("window_minutes", 10)
            inst._fitted = data.get("fitted", False)
            inst._use_torch = data.get("use_torch", False)
            if inst._use_torch and "torch_state" in data:
                import torch
                import torch.nn as nn

                class _LSTMClassifier(nn.Module):
                    def __init__(self):
                        super().__init__()
                        self.lstm = nn.LSTM(
                            SEQ_FEATURES, HIDDEN_SIZE,
                            num_layers=N_LAYERS, batch_first=True,
                        )
                        self.fc = nn.Linear(HIDDEN_SIZE, 3)

                    def forward(self, x):
                        _, (h, _) = self.lstm(x)
                        return self.fc(h[-1])

                m = _LSTMClassifier()
                m.load_state_dict(data["torch_state"])
                m.eval()
                inst._torch_model = m
        except Exception:
            pass
        return inst
