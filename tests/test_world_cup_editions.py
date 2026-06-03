from ingest.fixtures.world_cup import DEFAULT_WC_SEASONS, WC_EDITIONS, edition_label, missing_local_seasons


def test_wc_editions_span_1930_to_2022():
    assert min(WC_EDITIONS) == 1930
    assert max(WC_EDITIONS) == 2022
    assert len(WC_EDITIONS) == 22
    assert DEFAULT_WC_SEASONS == sorted(WC_EDITIONS.keys())


def test_edition_label():
    assert "1930" in edition_label(1930)
    assert "Brasil" in edition_label(1950)


def test_missing_local_seasons_returns_list():
    assert isinstance(missing_local_seasons(), list)
