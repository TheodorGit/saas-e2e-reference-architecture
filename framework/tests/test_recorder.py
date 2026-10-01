import json

import pytest

from framework.reporting.recorder import StepRecorder, describe, safe_name

pytestmark = pytest.mark.unit


def boom():
    raise AssertionError("Sent 3, expected 4")


def test_a_passing_step_records_its_expectation_and_result():
    rec = StepRecorder("s", "t.py::test_a")
    assert rec.step("count", lambda: 4, "Four were sent") == 4
    step = rec.steps[0]
    assert step["status"] == "passed" and step["message"] == "Four were sent"
    assert step["data"]["result"] == 4


def test_a_reading_says_what_it_found_in_words():
    rec = StepRecorder("s", "t::n")
    rec.step("Read the balance", lambda: 99573, "the balance before acting",
             found=lambda value: f"{value:,} units")
    rec.soft_step("Read the rows", lambda: 12, "the rows", found=lambda n: f"{n} rows")
    assert [s["message"] for s in rec.steps] == ["99,573 units", "12 rows"]
    assert rec.steps[0]["data"]["result"] == 99573


def test_found_is_not_used_when_the_step_fails():
    rec = StepRecorder("s", "t::n")
    rec.soft_step("Read the balance", lambda: (_ for _ in ()).throw(ValueError("no data")),
                  "the balance before acting", found=lambda value: f"{value} units")
    assert rec.steps[0]["message"] == "no data"
    assert rec.steps[0]["expected"] == "the balance before acting"


def test_a_failing_step_records_expected_instead_and_means():
    rec = StepRecorder("s", "t.py::test_a")
    with pytest.raises(AssertionError):
        rec.step("count", boom, "Four were sent", means="A recipient was skipped.")
    step = rec.steps[0]
    assert step["status"] == "failed"
    assert step["expected"] == "Four were sent"
    assert step["message"] == "Sent 3, expected 4"
    assert step["means"] == "A recipient was skipped."


def test_means_falls_back_to_the_exception_class():
    rec = StepRecorder("s", "t.py::test_a")
    with pytest.raises(AssertionError):
        rec.step("count", boom, "Four were sent")
    assert "did not match what this run did" in rec.steps[0]["means"]


def test_soft_steps_run_on_and_fail_once_at_the_end():
    rec = StepRecorder("s", "t.py::test_a")
    rec.soft_step("first", boom, "one")
    rec.soft_step("second", lambda: "ok", "two")
    assert [s["status"] for s in rec.steps] == ["failed", "passed"]
    with pytest.raises(AssertionError, match="1 independent check"):
        rec.raise_soft_failures()


def test_skips_and_known_issues_are_recorded_not_dropped():
    rec = StepRecorder("s", "t.py::test_a")
    rec.skip_step("inbox", "no inbox configured", "Mail arrives")
    rec.known_issue("ingest", "Report reads 1 short, a known undercount")
    assert [s["status"] for s in rec.steps] == ["skipped", "known_issue"]


def test_finalize_turns_completed_into_failed_when_a_step_failed(tmp_path):
    rec = StepRecorder("s", "t.py::test_a")
    rec.soft_step("first", boom, "one")
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
