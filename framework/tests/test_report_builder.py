import json
import re

import pytest

from framework.reporting import profiles
from framework.reporting.recorder import StepRecorder
from framework.reporting.report_builder import build, load_run, write_latest

pytestmark = pytest.mark.unit

PASS_ID = "suite/actions/test_send.py::test_send"
FAIL_ID = "suite/verification/test_totals.py::test_totals"
SKIP_ID = "suite/actions/test_skip.py::test_skip"


@pytest.fixture(autouse=True)
def profile():
    profiles.clear()
    profiles.register(profiles.SuiteProfile(
        key="demo", path_prefix="suite/", title="Demo run",
        sections=[("Sending", ["test_send", "test_skip"]), ("Totals", ["test_totals"])],
        titles={"test_send": "Send reaches the inbox"},
        facts=lambda run_dir, tests: [("Tests", len(tests))]))
    yield
    profiles.clear()


def write_run(run_dir, tests, extra_steps=()):
    manifest = {"run_id": "r1", "started": "2026-09-30T10:00:00+00:00",
                "finished": "2026-09-30T10:05:00+00:00", "duration": 300,
                "environment": "local", "interrupted": False, "tests": tests}
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    for rec in extra_steps:
        rec.save(run_dir)


def entry(nodeid, status, failure=None, skip_reason=None):
    return {"nodeid": nodeid, "func": nodeid.split("::")[1], "status": status,
            "duration": 1.0, "failure": failure, "skip_reason": skip_reason}


def failing_recorder():
    rec = StepRecorder("demo", FAIL_ID)
    try:
        rec.step("sent_total", lambda: (_ for _ in ()).throw(
            AssertionError("Journal charged 5, run spent 4")),
            "Journal charges exactly what the run spent",
            means="The run was charged for something it did not do.")
    except AssertionError:
        pass
    rec.finalize("completed")
    return rec


def test_the_manifest_is_the_authority_even_without_step_files(tmp_path):
    write_run(tmp_path, [entry(PASS_ID, "passed"),
                         entry(FAIL_ID, "failed", failure="E   RuntimeError: fixture died")])
    run = load_run(tmp_path)
    assert run["counts"]["total"] == 2 and run["verdict"] == "failed"
    failed = next(t for t in run["tests"] if t["status"] == "failed")
    assert failed["steps"] == []


def test_verdict_precedence_failed_then_skipped_then_passed(tmp_path):
    write_run(tmp_path, [entry(PASS_ID, "passed"), entry(SKIP_ID, "skipped",
                                                          skip_reason="no inbox")])
    assert load_run(tmp_path)["verdict"] == "skipped"


def test_titles_sections_and_facts_come_from_the_profile(tmp_path):
    write_run(tmp_path, [entry(PASS_ID, "passed"), entry(FAIL_ID, "failed", failure="E x")])
    run = load_run(tmp_path)
    send = next(t for t in run["tests"] if t["nodeid"] == PASS_ID)
    assert send["title"] == "Send reaches the inbox" and send["section"] == "Sending"
    assert run["suite_title"] == "Demo run" and run["facts"] == [("Tests", 2)]


def test_steps_attach_by_nodeid_and_orphans_are_reported(tmp_path):
    orphan = StepRecorder("demo", "suite/gone.py::test_gone")
    orphan.finalize("completed")
    write_run(tmp_path, [entry(FAIL_ID, "failed", failure="E x")],
              extra_steps=[failing_recorder(), orphan])
    run = load_run(tmp_path)
    assert len(run["tests"][0]["steps"]) == 1
    assert run["counts"]["orphan_step_files"] == ["suite/gone.py::test_gone"]


def test_the_red_report_says_what_was_expected_and_what_happened(tmp_path):
    write_run(tmp_path, [entry(PASS_ID, "passed"), entry(FAIL_ID, "failed", failure="E x")],
              extra_steps=[failing_recorder()])
    built = build(tmp_path)
    report = (tmp_path / "report.html").read_text()
    email = (tmp_path / "email.html").read_text()
    for page in (report, email):
        assert "Journal charges exactly what the run spent" in page
        assert "Journal charged 5, run spent 4" in page
        assert "The run was charged for something it did not do." in page
    assert built["subject"].startswith("[FAILED] Demo run: 1 of 2 tests failed")
    assert json.loads((tmp_path / "summary.json").read_text())["verdict"] == "failed"


def test_the_full_error_is_in_the_report_whole_and_folded(tmp_path):
    failure = "E  FIRST LINE of the failure\n" + "detail line\n" * 3000 + "E  LAST LINE"
    rec = StepRecorder("demo", FAIL_ID)
    long_error = "START of the step error " + "y" * 9000 + " END of the step error"
    with pytest.raises(AssertionError):
        rec.step("check", lambda: (_ for _ in ()).throw(AssertionError(long_error)), "right")
    rec.finalize("completed")
    write_run(tmp_path, [entry(FAIL_ID, "failed", failure=failure)], extra_steps=[rec])
    build(tmp_path)
    report = (tmp_path / "report.html").read_text()
    for part in ("FIRST LINE of the failure", "E  LAST LINE", "START of the step error",
                 "END of the step error"):
        assert part in report, f"{part!r} missing from the report"
    folded = re.search(r"<details[^>]*><summary[^>]*>Full error</summary><pre[^>]*>(.*?)</pre>"
                       r"</details>", report, re.DOTALL)
    assert folded, "the raw error is not folded under a 'Full error' toggle"
    assert "FIRST LINE of the failure" in folded.group(1)
    assert "detail line" not in (tmp_path / "email.html").read_text()


def test_explanations_sit_at_the_check_they_explain(tmp_path):
    rec = StepRecorder("demo", FAIL_ID)
    rec.step("open the page", lambda: None, "the page opens")
    rec.soft_step("totals match", lambda: (_ for _ in ()).throw(AssertionError("off by one")),
                  "totals equal the run", means="Billing does not match the run.")
    rec.known_issue("legacy counter", "counts one short; accepted until fixed")
    rec.step("close the page", lambda: None, "the page closes")
    rec.finalize("completed")
    write_run(tmp_path, [entry(FAIL_ID, "failed", failure="E  AssertionError: 1 failed")],
              extra_steps=[rec])
    build(tmp_path)
    report = (tmp_path / "report.html").read_text()
    at = {text: report.index(text) for text in (
        "open the page", "totals match", "WHY IT FAILED", "Billing does not match the run.",
        "legacy counter", "Known issue:", "close the page")}
    assert at["open the page"] < at["totals match"] < at["WHY IT FAILED"] \
        < at["Billing does not match the run."] < at["legacy counter"] \
        < at["Known issue:"] < at["close the page"], f"out of place: {at}"
    assert report.count("WHY IT FAILED") == 1
    assert report.count(">Check</th>") == 1 and report.count(">Result</th>") == 1
    assert re.search(r'<td style="[^"]*">totals match</td>', report), "check name not in its cell"
    assert not re.search(r'font-weight:700;[^>]*>totals match<', report), "check name is bold"


def test_a_passing_check_shows_what_it_confirmed_not_its_raw_value(tmp_path):
    rec = StepRecorder("demo", PASS_ID)
    rec.step("rows are well-formed", lambda: 383,
             "every row has an id, a reference and a whole amount", rows="383")
    rec.finalize("completed")
    write_run(tmp_path, [entry(PASS_ID, "passed")], extra_steps=[rec])
    build(tmp_path)
    report = (tmp_path / "report.html").read_text()
    assert "every row has an id, a reference and a whole amount" in report
    assert "383" not in report, "a bare value reached the report"
    saved = json.loads(next(tmp_path.glob("steps__*.json")).read_text())
    assert saved["steps"][0]["data"]["result"] == 383, "the raw value must stay in the file"


def test_latest_page_opens_the_newest_report_by_a_relative_link(tmp_path):
    older = tmp_path / "clean" / "run_1" / "report.html"
    newer = tmp_path / "some bug" / "run_2" / "report.html"
    page = tmp_path / "latest.html"
    write_latest(older, page)
    write_latest(newer, page)
    text = page.read_text()
    assert 'url=some%20bug/run_2/report.html"' in text and "run_1" not in text
    assert str(tmp_path) not in text, "the link must be relative, not a machine path"


def test_an_unregistered_test_is_still_reported(tmp_path):
    write_run(tmp_path, [entry("elsewhere/test_x.py::test_x", "passed")])
    run = load_run(tmp_path)
    assert run["tests"][0]["title"] == "test_x" and run["tests"][0]["section"] == "Other"
