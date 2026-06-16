"""Configuração compartilhada do pytest."""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "slow: testes pesados (treino ML, benchmarks completos, carga de artefato)",
    )
