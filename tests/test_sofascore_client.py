from unittest.mock import MagicMock, patch

import pytest

from ingest.sofascore.client import SofascoreClient, SofascoreWafBlockedError


def _waf_response():
    resp = MagicMock()
    resp.status_code = 403
    resp.text = '{"error": {"code": 403, "reason": "challenge" }}'
    return resp


def test_waf_blocked_property():
    client = SofascoreClient(min_interval_sec=0.0)
    client._waf_fail_fast_after = 2
    client._consecutive_waf_blocks = 2
    assert client.waf_blocked is True


def test_success_resets_waf_counter():
    client = SofascoreClient(min_interval_sec=0.0)
    client._waf_fail_fast_after = 2
    client._waf_max_retries = 0
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"events": []}

    with patch.object(client._session, "get", side_effect=[_waf_response(), ok]):
        with pytest.raises(SofascoreWafBlockedError):
            client.get_json("event/1")
        payload = client.get_json("event/2")
        assert payload == {"events": []}
        assert client._consecutive_waf_blocks == 0


def test_probe_returns_false_on_waf():
    client = SofascoreClient(min_interval_sec=0.0)
    client._waf_max_retries = 0
    with patch.object(client._session, "get", return_value=_waf_response()):
        assert client.probe() is False
