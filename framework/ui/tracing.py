"""Videos, traces and screens of browser tests."""
from pathlib import Path

from framework.reporting import evidence
from framework.reporting.recorder import FAILED, StepRecorder

TRACE_FILE = evidence.TRACE_FILE
VIDEOS_DIR = "videos"
NO_PAGE = ("", "about:blank")


class Evidence:
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

    def started(self, name: str):
        self._close_group()
        self.context.tracing.group(name)
        self._group_open = True

    def finished(self, step: dict, number: int):
        self._close_group()
        if not step.get("ui") or self.page.url in NO_PAGE:
            return
        png = self.page.screenshot()
        if png == self._last and step.get("status") != FAILED:
            return
        self._last = png
        self.shots.append((evidence.check_file(number), png))

    def _close_group(self):
        if self._group_open:
            self._group_open = False
            self.context.tracing.group_end()

    def needed(self, test_failed: bool) -> bool:
        steps = self.recorder.steps
        ui_failed = any(s.get("ui") and s.get("status") == FAILED for s in steps)
        no_check_failed = not any(s.get("status") == FAILED for s in steps)
        return ui_failed or (test_failed and no_check_failed)

    def stop(self, run_dir: Path, test_failed: bool) -> Path | None:
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
        folder = run_dir / VIDEOS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        base = evidence.folder_name(self.recorder)
        target, n = folder / f"{base}.webm", 2
        while target.exists():
            target, n = folder / f"{base}_{n}.webm", n + 1
        video.save_as(str(target))
        video.delete()
        self.recorder.add_metadata("video", f"{VIDEOS_DIR}/{target.name}")


def failed(recorder: StepRecorder, node) -> bool:
    phases = any(getattr(getattr(node, f"rep_{when}", None), "failed", False)
                 for when in ("setup", "call"))
    return phases or any(s.get("status") == FAILED for s in recorder.steps)
