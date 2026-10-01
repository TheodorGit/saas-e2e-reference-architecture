"""What a browser test showed: a video of every browser test, and - when a UI check
failed - the Playwright trace and the screen after each UI check.

pytest-playwright's --tracing and --video options only cover its own `context`
fixture. A suite that builds contexts itself (to reuse a login's session, say)
gets none of it unless it collects it.

Every browser test keeps its video, passed or failed, so a person can watch what
the run did: videos/<test name>.webm, linked from the test in the report.

Screen EVIDENCE answers "what was on screen when it went wrong", so it is kept
only when that is the question: when a UI check (a step marked ui=True) failed, or
the test broke outside any check. An inbox, API or reconciliation failure keeps
what THAT check saw instead (framework/reporting/evidence.py).

    evidence/test_bulk_tag_chromium/
        00_trace.zip                  every action, grouped by check
                                      (open with playwright show-trace)
        01_filter by tag.png          the screen after each UI check,
        02_check failed - bulk add a tag.png   numbered by the check's position

A screen is taken only after a UI check, never before a page is open, and not
when identical to the last one kept - except a failed check's, always kept.
"""
from pathlib import Path

from framework.reporting import evidence
from framework.reporting.recorder import FAILED, StepRecorder, safe_name

TRACE_FILE = "00_trace.zip"
VIDEOS_DIR = "videos"
NO_PAGE = ("", "about:blank")


class Evidence:
    """Collects screen evidence for one test's page; keeps it only when needed."""

    def __init__(self, context, page, recorder: StepRecorder):
        self.context = context
        self.page = page
        self.recorder = recorder
        self.shots: list[tuple[str, bytes]] = []
        self._last: bytes | None = None
        self._group_open = False
        context.tracing.start(title=evidence.title_of(recorder), screenshots=True,
                              snapshots=True, sources=True)
        recorder.watch(self)

    # --- StepRecorder watcher ---------------------------------------------------

    def started(self, name: str):
        self._close_group()
        self.context.tracing.group(name)
        self._group_open = True

    def finished(self, step: dict, number: int):
        self._close_group()
        if not step.get("ui") or self.page.url in NO_PAGE:
            return  # not a screen check, or nothing on screen yet
        png = self.page.screenshot()
        if png == self._last and step.get("status") != FAILED:
            return  # unchanged since the last screen kept
        self._last = png
        self.shots.append((evidence.check_file(number, step), png))

    def _close_group(self):
        if self._group_open:
            self._group_open = False
            self.context.tracing.group_end()

    # --- the end of the test ------------------------------------------------------

    def needed(self, test_failed: bool) -> bool:
        """A UI check failed, or the test broke where no check could say why."""
        steps = self.recorder.steps
        ui_failed = any(s.get("ui") and s.get("status") == FAILED for s in steps)
        no_check_failed = not any(s.get("status") == FAILED for s in steps)
        return ui_failed or (test_failed and no_check_failed)

    def stop(self, run_dir: Path, test_failed: bool) -> Path | None:
        """Finish the trace, close the context (which finishes the video), save
        the video, and keep the screen evidence only when it is needed."""
        self._close_group()
        keep = self.needed(test_failed)
        folder = evidence.folder_for(self.recorder, run_dir) if keep else None
        self.context.tracing.stop(path=str(folder / TRACE_FILE) if keep else None)
        video = getattr(self.page, "video", None)
        self.context.close()
        if video:
            self._keep_video(video, Path(run_dir))
        if keep:
            for name, png in self.shots:
                (folder / name).write_bytes(png)
        return folder

    def _keep_video(self, video, run_dir: Path):
        """videos/<test name>.webm, recorded on the test so the report links it."""
        folder = run_dir / VIDEOS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        base = safe_name(self.recorder.nodeid.split("::")[-1])
        target, n = folder / f"{base}.webm", 2
        while target.exists():
            target, n = folder / f"{base}_{n}.webm", n + 1
        video.save_as(str(target))
        video.delete()
        self.recorder.add_metadata("video", f"{VIDEOS_DIR}/{target.name}")


def failed(recorder: StepRecorder, node) -> bool:
    """A test failed if a phase failed or it holds a failed step (which the
    steps fixture will raise in teardown, after the evidence is collected)."""
    phases = any(getattr(getattr(node, f"rep_{when}", None), "failed", False)
                 for when in ("setup", "call"))
    return phases or any(s.get("status") == FAILED for s in recorder.steps)
