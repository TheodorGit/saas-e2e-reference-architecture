"""The API recorder, docs coverage, and the teardown that forbids a held failure."""
import json

import pytest
import requests

from framework.api.coverage import assert_exercised, gaps
from framework.api.recorder import ApiRecorder, Coverage
from framework.reporting.recorder import FAILED, PASSED, StepRecorder

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, status: int, text: str = "{}"):
        self.status_code = status
        self.text = text


class FakeHttp:
    """Answers by 'METHOD url'; raises for anything it does not know."""

    def __init__(self, answers: dict):
        self.answers = answers
        self.seen = []

    def request(self, method, url, **_):
        self.seen.append(f"{method} {url}")
        answer = self.answers.get(f"{method} {url}")
        if answer is None:
            raise requests.ConnectionError(f"nothing at {url}")
        return FakeResponse(*answer)


def recorder(answers: dict, steps=None, coverage=None):
    return ApiRecorder(FakeHttp(answers), "http://h/", steps or StepRecorder("t", "t::n"),
                       coverage or Coverage(), "t::n")


def test_calls_are_steps_counted_by_route_template():
    coverage = Coverage()
    api = recorder({"GET http://h/items/7": (200,), "DELETE http://h/items/7": (500, "boom")},
                   coverage=coverage)
    assert api.call("GET", "/items/{item_id}", item_id=7).status_code == 200
    assert api.call("DELETE", "/items/{item_id}", item_id=7).status_code == 500
    assert [s["status"] for s in api.steps.steps] == [PASSED, FAILED]
    assert "answered 500, expected 200: boom" in api.steps.steps[1]["message"]
    assert coverage.executed() == {"GET /items/{item_id}", "DELETE /items/{item_id}"}


def test_a_failed_call_keeps_the_exchange_as_evidence(tmp_path):
    from framework.reporting.evidence import save_attachments
    api = recorder({"GET http://h/ok": (200,), "DELETE http://h/items/7": (500, "boom")})
    api.call("GET", "/ok")
    api.call("DELETE", "/items/{item_id}", item_id=7)
    written = save_attachments(api.steps, tmp_path)
    assert [p.name for p in written] == [
        "02_check failed - DELETE _items_{item_id} - request and response.txt"]
    assert "HTTP 500" in written[0].read_text() and "boom" in written[0].read_text()


def test_a_failed_request_is_a_failed_step_and_not_coverage():
    api = recorder({})
    assert api.call("GET", "/down") is None
    assert api.steps.steps[0]["status"] == FAILED
    assert api.coverage.executed() == set()
    with pytest.raises(AssertionError, match="1 independent check"):
        api.steps.raise_soft_failures()


def test_checks_are_soft():
    api = recorder({})
    api.check("first", lambda: (_ for _ in ()).throw(AssertionError("wrong")), "right")
    api.check("second", lambda: 1, "one")
    assert [s["status"] for s in api.steps.steps] == [FAILED, PASSED]


def test_docs_coverage_names_both_sides():
    coverage = Coverage()
    api = recorder({"GET http://h/a": (200,), "GET http://h/extra": (200,)}, coverage=coverage)
    api.call("GET", "/a")
    api.call("GET", "/extra")
    documented = [("GET", "/a"), ("post", "/b")]
    assert gaps(documented, coverage) == (["post /b"], ["get /extra"])
    with pytest.raises(AssertionError) as caught:
        assert_exercised(documented, coverage)
    assert "no test executed them this session: ['post /b']" in str(caught.value)
    assert "executed but not documented: ['get /extra']" in str(caught.value)


def test_coverage_of_nothing_fails():
    with pytest.raises(AssertionError, match="proves nothing"):
        assert_exercised([], Coverage())


def test_full_coverage_passes():
    coverage = Coverage()
    recorder({"GET http://h/a": (200,)}, coverage=coverage).call("GET", "/a")
    assert assert_exercised([("GET", "/a")], coverage) == \
        "all 1 documented endpoints executed this session"


HOLDING = """
from framework.api.recorder import ApiRecorder

class Http:
    def request(self, method, url, **_):
        class R:
            status_code = 500
            text = "server error"
        return R()

def test_holds_a_failure(api_recorder):
    api = api_recorder(Http(), "http://h")
    api.call("GET", "/thing")
    # the body ends without raising anything

def test_holds_a_soft_step(steps):
    steps.soft_step("ui check", lambda: (_ for _ in ()).throw(AssertionError("wrong")),
                    "right")
    # no raise_soft_failures(): the teardown must fail it anyway

def test_raises_its_own(steps):
    steps.soft_step("ui check", lambda: (_ for _ in ()).throw(AssertionError("wrong")),
                    "right")
    steps.raise_soft_failures()

def test_clean(api_recorder):
    pass
"""


def test_a_test_cannot_pass_while_holding_a_failed_step(pytester, monkeypatch):
    monkeypatch.setenv("E2E_RESULTS_DIR", str(pytester.path / "reports"))
    monkeypatch.delenv("E2E_REPORT_TO", raising=False)
    pytester.makeconftest('pytest_plugins = ["framework.pytest_plugin"]\n')
    pytester.makepyfile(test_hold=HOLDING)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    # Held failures: body passed, teardown errors. Raised in the body: failed once.
    result.assert_outcomes(passed=3, failed=1, errors=2)
    run_dir = next((pytester.path / "reports").glob("run_*"))
    manifest = json.loads((run_dir / "manifest.json").read_text())
    status = {t["func"]: t["status"] for t in manifest["tests"]}
    assert status == {"test_holds_a_failure": "failed", "test_holds_a_soft_step": "failed",
                      "test_raises_its_own": "failed", "test_clean": "passed"}
    for name in ("holds_a_failure", "holds_a_soft_step"):
        steps = json.loads(next(run_dir.glob(f"steps__*{name}*.json")).read_text())
        assert steps["status"] == "failed"
