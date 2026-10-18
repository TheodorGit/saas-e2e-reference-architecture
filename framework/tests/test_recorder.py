import json

import pytest

from framework.reporting.recorder import CheckRecorder, describe, safe_name

pytestmark = pytest.mark.unit


def boom():
    raise AssertionError("Sent 3, expected 4")


def test_a_passing_check_records_its_expectation_and_result():
    rec = CheckRecorder("s", "t.py::test_a")
    assert rec.check("count", lambda: 4, "Four were sent") == 4
    check = rec.checks[0]
    assert check["status"] == "passed" and check["message"] == "Four were sent"
    assert check["data"]["result"] == 4


def test_a_reading_says_what_it_found_in_words():
    rec = CheckRecorder("s", "t::n")
    rec.check("Read the balance", lambda: 99573, "the balance before acting",
              found=lambda value: f"{value:,} units")
    rec.soft_check("Read the rows", lambda: 12, "the rows", found=lambda n: f"{n} rows")
    assert [s["message"] for s in rec.checks] == ["99,573 units", "12 rows"]
    assert rec.checks[0]["data"]["result"] == 99573


def test_found_is_not_used_when_the_check_fails():
    rec = CheckRecorder("s", "t::n")
    rec.soft_check("Read the balance", lambda: (_ for _ in ()).throw(ValueError("no data")),
                   "the balance before acting", found=lambda value: f"{value} units")
    assert rec.checks[0]["message"] == "no data"
    assert rec.checks[0]["expected"] == "the balance before acting"


def test_a_failing_check_records_expected_instead_and_means():
    rec = CheckRecorder("s", "t.py::test_a")
    with pytest.raises(AssertionError):
        rec.check("count", boom, "Four were sent", means="A recipient was skipped.")
    check = rec.checks[0]
    assert check["status"] == "failed"
    assert check["expected"] == "Four were sent"
    assert check["message"] == "Sent 3, expected 4"
    assert check["means"] == "A recipient was skipped."


def test_means_falls_back_to_the_exception_class():
    rec = CheckRecorder("s", "t.py::test_a")
    with pytest.raises(AssertionError):
        rec.check("count", boom, "Four were sent")
    assert "did not match what this run did" in rec.checks[0]["means"]


def test_soft_checks_run_on_and_fail_once_at_the_end():
    rec = CheckRecorder("s", "t.py::test_a")
    rec.soft_check("first", boom, "one")
    rec.soft_check("second", lambda: "ok", "two")
    assert [s["status"] for s in rec.checks] == ["failed", "passed"]
    with pytest.raises(AssertionError, match="1 independent check"):
        rec.raise_soft_failures()


def test_a_soft_failure_marks_the_check_that_failed_and_only_that_one():
    rec = CheckRecorder("s", "t.py::test_a")
    rec.check("first", lambda: "ok", "one")
    rec.soft_check("second", boom, "two")
    assert "soft" not in rec.checks[0] and rec.checks[1]["soft"] is True


def test_a_soft_failure_that_recorded_no_check_still_fails_the_test(monkeypatch):
    rec = CheckRecorder("s", "t.py::test_a")
    monkeypatch.setattr(rec, "check", lambda *_, **__: boom())
    assert rec.soft_check("second", lambda: "ok", "two") is None
    with pytest.raises(AssertionError, match="1 independent check"):
        rec.raise_soft_failures()


def test_skips_and_known_issues_are_recorded_not_dropped():
    rec = CheckRecorder("s", "t.py::test_a")
    rec.skip_check("inbox", "no inbox configured", "Mail arrives")
    rec.known_issue("ingest", "Report reads 1 short, a known undercount")
    assert [s["status"] for s in rec.checks] == ["skipped", "known_issue"]


def test_finalize_turns_completed_into_failed_when_a_check_failed(tmp_path):
    rec = CheckRecorder("s", "t.py::test_a")
    rec.soft_check("first", boom, "one")
    rec.finalize("completed")
    data = json.loads(rec.save(tmp_path).read_text())
    assert data["status"] == "failed" and data["nodeid"] == "t.py::test_a"


def test_an_empty_assert_is_described_by_where_it_raised():
    # What a bare `assert` raises outside pytest's rewriting (in a page object).
    try:
        raise AssertionError()
    except AssertionError as exc:
        text = describe(exc)
    assert text.startswith("AssertionError at test_recorder.py:")
    assert "raise AssertionError()" in text


def test_long_nodeids_get_a_short_stable_file_name():
    nodeid = "t.py::test_a[" + "x" * 300 + "]"
    assert safe_name(nodeid) == safe_name(nodeid)
    assert len(safe_name(nodeid)) < 140
