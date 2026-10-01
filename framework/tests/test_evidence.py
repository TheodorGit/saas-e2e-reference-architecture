"""Evidence of the kind each failed check was about, and nothing else."""
import json
from urllib.parse import quote

import pytest

from framework.reporting import evidence
from framework.reporting.recorder import StepRecorder
from framework.reporting.report_builder import build
from framework.ui import tracing

pytestmark = pytest.mark.unit

NODEID = "suite/actions/test_send.py::test_send[chromium]"


class FakeTracing:
    def __init__(self):
        self.calls = []

    def start(self, **options):
        self.calls.append(("start", options.get("title")))

    def group(self, name):
        self.calls.append(("group", name))

    def group_end(self):
        self.calls.append(("group_end",))

    def stop(self, path=None):
        self.calls.append(("stop", path))
        if path:
            open(path, "wb").write(b"zip")


class FakeContext:
    def __init__(self):
        self.tracing = FakeTracing()
        self.closed = False

    def close(self):
        self.closed = True


class FakeVideo:
    def __init__(self):
        self.saved, self.deleted = None, False

    def save_as(self, path):
        self.saved = path
        open(path, "wb").write(b"webm")

    def delete(self):
        self.deleted = True


class FakePage:
    """Each screenshot shows a new screen, unless `screens` says otherwise."""

    def __init__(self, screens=None, url="http://app/"):
        self.shots = 0
        self.screens = list(screens or [])
        self.url = url
        self.video = FakeVideo()

    def screenshot(self):
        self.shots += 1
        return self.screens.pop(0) if self.screens else f"png{self.shots}".encode()


def fail(message):
    return lambda: (_ for _ in ()).throw(AssertionError(message))


def browser_test(page=None):
    context, page = FakeContext(), page or FakePage()
    steps = StepRecorder("demo", NODEID)
    return context, page, steps, tracing.Evidence(context, page, steps)


# --- screens: UI checks only ---------------------------------------------------

def test_only_ui_checks_get_a_screen_and_only_once_a_page_is_open():
    context, page, steps, ui = browser_test(FakePage(url="about:blank"))
    steps.step("the audience is ours", lambda: None, "ours", ui=True)
    page.url = "http://app/#/list"
    steps.step("the API has it", lambda: None, "stored")
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)
    assert [name for name, _ in ui.shots] == ["03_the list shows it sent.png"]
    assert context.tracing.calls[:3] == [("start", "test_send"), ("group", "the audience is ours"),
                                         ("group_end",)]


def test_an_unchanged_screen_is_skipped_but_a_failed_one_is_always_kept():
    _, _, steps, ui = browser_test(FakePage(screens=[b"list", b"list", b"list"]))
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)
    steps.step("the badge says sent", lambda: None, "sent", ui=True)
    steps.soft_step("the chips show the server's truth", fail("still pending"), "truth", ui=True)
    assert [name for name, _ in ui.shots] == [
        "01_the list shows it sent.png", "03_check failed - the chips show the server's truth.png"]


# --- when screen evidence is kept ------------------------------------------------

def test_a_failed_ui_check_keeps_trace_and_screens_as_evidence(tmp_path):
    _, page, steps, ui = browser_test()
    steps.step("filter by tag", lambda: None, "filtered", ui=True)
    steps.soft_step("bulk add a tag", fail("still pending"), "not pending", ui=True)
    folder = ui.stop(tmp_path, tracing.failed(steps, node=None))
    assert folder == tmp_path / "evidence" / "test_send_chromium"
    assert sorted(p.name for p in folder.iterdir()) == [
        "00_trace.zip", "01_filter by tag.png", "02_check failed - bulk add a tag.png",
        "test.txt"]
    assert (folder / "test.txt").read_text().splitlines()[0] == NODEID


def test_every_browser_test_keeps_its_video_and_the_report_can_find_it(tmp_path):
    _, page, steps, ui = browser_test()
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)
    ui.stop(tmp_path, tracing.failed(steps, node=None))
    assert (tmp_path / "videos" / "test_send_chromium.webm").read_bytes() == b"webm"
    assert steps.metadata["video"] == "videos/test_send_chromium.webm"
    assert page.video.deleted, "the temporary recording must be removed once saved"


def test_an_inbox_failure_keeps_no_screen_evidence(tmp_path):
    context, page, steps, ui = browser_test()
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)
    steps.soft_step("the suppressed contact got nothing", fail("they got it"), "nothing")
    assert ui.stop(tmp_path, tracing.failed(steps, node=None)) is None
    assert not (tmp_path / "evidence").exists()
    assert context.tracing.calls[-1] == ("stop", None) and context.closed


def test_a_break_outside_any_check_keeps_screen_evidence(tmp_path):
    _, _, steps, ui = browser_test()
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)
    folder = ui.stop(tmp_path, test_failed=True)
    assert (folder / "00_trace.zip").exists()


def test_a_pass_keeps_only_its_video(tmp_path):
    _, _, steps, ui = browser_test()
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)
    assert ui.stop(tmp_path, tracing.failed(steps, node=None)) is None
    assert not (tmp_path / "evidence").exists()
    assert [p.name for p in (tmp_path / "videos").iterdir()] == ["test_send_chromium.webm"]


# --- what a failed check saw -------------------------------------------------------

def test_a_failed_check_keeps_what_it_saw_and_a_passed_one_keeps_nothing(tmp_path):
    steps = StepRecorder("demo", NODEID)

    def leaked():
        steps.attach("the email they received", "<p>Hello</p>", "html")
        steps.attach("the email they received", b"Subject: hi", "eml")
        raise AssertionError("they got it")

    def delivered():
        steps.attach("the email", "<p>fine</p>", "html")
    steps.step("each copy arrived", delivered, "arrived")
    steps.soft_step("the suppressed contact got nothing", leaked, "nothing")
    written = evidence.save_attachments(steps, tmp_path)
    assert sorted(p.name for p in written) == [
        "02_check failed - the suppressed contact got nothing - the email they received.eml",
        "02_check failed - the suppressed contact got nothing - the email they received.html"]
    assert written[0].parent == tmp_path / "evidence" / "test_send_chromium"


def test_file_names_cannot_be_read_backwards_or_break_a_path():
    passed = evidence.check_file(4, {"step": "the list shows it sent", "status": "passed"})
    failed = evidence.check_file(6, {"step": 'nobody "else" got it?', "status": "failed"},
                                 "the email", "html")
    assert passed == "04_the list shows it sent.png"
    assert failed == "06_check failed - nobody _else_ got it - the email.html"


LONG_CHECK = ("every billed action has a row, and no row is unexplained, read from the journal "
              "after the whole run has settled and every charge has had time to land")


def test_a_run_token_in_a_name_is_cut_to_its_slug(monkeypatch):
    monkeypatch.setenv("E2E_NAME_PREFIX", "QA")
    address = "qa+qa-1001_1320ae98-unsub-oneclick-d2b6c8@example.com"
    name = evidence.check_file(2, {"step": f"{address}: unsubscribe as click",
                                   "status": "failed"}, "the report the API returned", "json")
    assert name == ("02_check failed - unsub-oneclick_ unsubscribe as click - "
                    "the report the API returned.json")


def test_a_long_name_is_cut_in_the_middle_and_keeps_its_label():
    name = evidence.check_file(3, {"step": LONG_CHECK, "status": "failed"},
                               "the journal rows and the run's record", "json")
    assert len(name) <= evidence.FILE_MAX
    assert name.startswith("03_check failed - every billed")
    assert "~" in name and "time to land - the journal rows and the run's record.json" in name


def test_a_shortened_name_is_still_linked_by_its_label(tmp_path):
    steps = StepRecorder("demo", NODEID)

    def wrong():
        steps.attach("the rows it read", "[]", "json")
        raise AssertionError("one row short")
    steps.soft_step(LONG_CHECK, wrong, "every row")
    steps.finalize("completed")
    steps.save(tmp_path)
    written = evidence.save_attachments(steps, tmp_path)
    manifest = {"run_id": "r1", "started": "2026-10-01T10:00:00+00:00",
                "finished": "2026-10-01T10:01:00+00:00", "duration": 60,
                "environment": "local", "interrupted": False,
                "tests": [{"nodeid": NODEID, "func": "test_send", "status": "failed",
                           "duration": 1.0, "failure": "E  AssertionError: 1 failed",
                           "skip_reason": None}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    build(tmp_path)
    report = (tmp_path / "report.html").read_text()
    href = quote(f"evidence/test_send_chromium/{written[0].name}")
    assert len(written[0].name) <= evidence.FILE_MAX
    assert f'href="{href}">the rows it read (.json)</a>' in report


def test_two_tests_with_one_name_get_two_folders(tmp_path):
    first = evidence.folder_for(StepRecorder("demo", NODEID), tmp_path)
    second = evidence.folder_for(StepRecorder("demo", "other/test_send.py::test_send[chromium]"),
                                 tmp_path)
    assert (first.name, second.name) == ("test_send_chromium", "test_send_chromium_2")


# --- the report ----------------------------------------------------------------------

def test_the_report_links_each_check_to_its_own_evidence(tmp_path):
    _, _, steps, ui = browser_test()
    steps.step("the list shows it sent", lambda: None, "sent", ui=True)

    def leaked():
        steps.attach("the email they received", "<p>Hello</p>", "html")
        raise AssertionError("they got it")
    steps.soft_step("bulk add a tag", fail("still pending"), "not pending", ui=True)
    steps.soft_step("the suppressed contact got nothing", leaked, "nothing")
    steps.finalize("completed")
    ui.stop(tmp_path, test_failed=True)
    steps.save(tmp_path)
    evidence.save_attachments(steps, tmp_path)
    manifest = {"run_id": "r1", "started": "2026-09-30T10:00:00+00:00",
                "finished": "2026-09-30T10:01:00+00:00", "duration": 60,
                "environment": "local", "interrupted": False,
                "tests": [{"nodeid": NODEID, "func": "test_send", "status": "failed",
                           "duration": 1.0, "failure": "E  AssertionError: 2 failed",
                           "skip_reason": None}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    build(tmp_path)
    report = (tmp_path / "report.html").read_text()
    folder = "evidence/test_send_chromium"
    assert 'href="videos/test_send_chromium.webm">Watch this test' in report
    assert f'href="{folder}/00_trace.zip">the trace' in report
    email = (f'{folder}/03_check%20failed%20-%20the%20suppressed%20contact%20got%20nothing'
             f'%20-%20the%20email%20they%20received.html')
    assert f'href="{email}">the email they received (.html)' in report
    assert report.index("bulk add a tag") < report.index("02_check%20failed") \
        < report.index("the suppressed contact got nothing") < report.index(email), \
        "evidence is not in its own check's row"
