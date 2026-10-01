"""Smoke: driven by the API's own index, every documented read answers with a
token and refuses without one."""
import pytest

pytestmark = pytest.mark.api


def test_api_smoke(v1, v1_anon):
    index = v1_anon.call("GET", "/v1/")
    endpoints = index.json()["endpoints"] if index is not None else []
    v1.check("the index lists endpoints", lambda: _some(endpoints, "endpoints"),
             expected="a non-empty index, readable without a token")
    # Reads with no path parameter can be called blind; the rest need data (full tests).
    blind = [e["path"] for e in endpoints
             if e["method"] == "GET" and e["auth"] == "bearer" and "{" not in e["path"]]
    v1.check("the index lists reads to call", lambda: _some(blind, "token-protected reads"),
             expected="at least one read to smoke, so the smoke is not empty")
    for path in blind:
        v1.call("GET", path, expect=200)
        v1_anon.call("GET", path, expect=401)


def _some(items: list, what: str) -> int:
    assert items, f"the index lists no {what}"
    return len(items)
