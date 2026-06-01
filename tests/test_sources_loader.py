from pathlib import Path

import pytest
import yaml

from ingest.sources_loader import load_sources


def test_load_sources_from_yaml(tmp_path: Path):
    config = {
        "sources": [
            {"id": "test_a", "name": "Test A", "url": "https://example.com/a.xml"},
            {"id": "test_b", "name": "Test B", "url": "https://example.com/b.xml", "enabled": False},
        ]
    }
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.dump(config), encoding="utf-8")

    sources = load_sources(path)
    assert len(sources) == 1
    assert sources[0].source == "test_a"
    assert sources[0].name == "Test A"


def test_load_project_sources():
    sources = load_sources(Path("data/sources.yaml"))
    ids = {s.source for s in sources}
    assert "globo_esporte" in ids
    assert "fogaonet" in ids
    assert "gazeta_esportiva" in ids
    assert "lance" not in ids
