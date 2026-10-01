import json
from types import SimpleNamespace

import pytest

from framework.pipeline.manifest import RunManifest

pytestmark = pytest.mark.unit


def phase(nodeid, when, outcome="passed", longrepr=None, duration=0.1):
    return SimpleNamespace(nodeid=nodeid, when=when, duration=duration,
                           failed=outcome == "failed", skipped=outcome == "skipped",
                           passed=outcome == "passed", longrepr=longrepr,
                           longreprtext=str(longrepr or ""))


def test_a_complete_pass_is_passed():
    manifest = RunManifest("r1")
    for when in ("setup", "call", "teardown"):
        manifest.record(phase("t.py::test_a", when), "test_a")
    assert manifest.snapshot(final=True)["tests"][0]["status"] == "passed"


def test_a_teardown_failure_fails_the_test():
    manifest = RunManifest("r1")
    manifest.record(phase("t.py::test_a", "call"), "test_a")
    manifest.record(phase("t.py::test_a", "teardown", "failed", "E  boom"), "test_a")
    entry = manifest.snapshot(final=True)["tests"][0]
    assert entry["status"] == "failed" and "boom" in entry["failure"]


def test_a_long_failure_is_kept_whole():
    text = "E  FIRST LINE of a long failure\n" + "x = 1\n" * 3000 + "E  LAST LINE"
    manifest = RunManifest("r1")
    manifest.record(phase("t.py::test_a", "call", "failed", text), "test_a")
    assert manifest.snapshot(final=True)["tests"][0]["failure"] == text


def test_a_test_still_running_is_never_reported_as_passed():
    manifest = RunManifest("r1")
    manifest.record(phase("t.py::test_a", "setup"), "test_a")
    entry = manifest.snapshot(final=False)["tests"][0]
    assert entry["status"] == "skipped"
    assert "interrupted" in entry["skip_reason"]


def test_skip_reason_is_kept():
    manifest = RunManifest("r1")
    manifest.record(phase("t.py::test_a", "setup", "skipped",
                          ("f.py", 3, "Skipped: no inbox")), "test_a")
    assert manifest.snapshot(final=True)["tests"][0]["skip_reason"] == "no inbox"


def test_write_produces_json(tmp_path):
    manifest = RunManifest("r1", environment="local")
    manifest.record(phase("t.py::test_a", "teardown"), "test_a")
    data = json.loads(manifest.write(tmp_path, final=True).read_text())
    assert data["run_id"] == "r1" and data["environment"] == "local"
    assert data["interrupted"] is False
