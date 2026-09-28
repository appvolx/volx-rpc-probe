"""Minimal smoke tests for volx-rpc-probe (no network required)."""

from src.probe import EndpointResult


def test_endpoint_result_avg():
    r = EndpointResult(url="https://example.com", ok=True, latencies_ms=[10.0, 20.0, 30.0])
    assert r.avg_ms == 20.0
    assert r.min_ms == 10.0
    assert r.max_ms == 30.0


def test_empty_latencies():
    r = EndpointResult(url="x", ok=False)
    assert r.avg_ms is None
