"""Recorded steps: every check declares what it expects before it runs.

A bare `assert` fails with an error and nothing else. A step fails with three
things the reader needs: what it EXPECTED (declared up front), what happened
INSTEAD (the real exception, first line), and what the failure MEANS in product
terms (authored, or classified from the exception type, or nothing at all).

Vocabulary:
  step          run a check; record it; re-raise on failure
  soft_step     run an INDEPENDENT check; record it; keep going. The test then
                ends with raise_soft_failures(), so nothing is swallowed - one
                wrong expectation just cannot hide the checks after it
  skip_step     record a check that did NOT run, and why. A check that never ran
                is a hole in coverage, not a pass, so it is reported
  known_issue   record a check that hit a known, accepted defect: amber, never
                green, never silent
  attach        inside a check: keep what the check saw (an email, a response,
                rows) as evidence - written out only if that check fails
  ui=True       on a step: the check confirms something on screen, so its screen
                is evidence (see framework/ui/tracing.py)
"""
import hashlib
import json
import re
import traceback
from datetime import UTC, datetime
from pathlib import Path

from framework.reporting.failure_reasons import classify

REASON_MAX = 300
# Windows paths cap near 260 characters; long parametrized nodeids get a digest.
NAME_MAX = 120

PASSED, FAILED, SKIPPED, KNOWN_ISSUE = "passed", "failed", "skipped", "known_issue"


def describe(exc: BaseException) -> str:
    """The failure reason: the exception's own first line. An assert with no
    message (common inside page objects, where pytest does not rewrite asserts)
    falls back to the exception type and the source line that raised it."""
    first = next((ln.strip() for ln in str(exc).splitlines() if ln.strip()), "")
    if first:
        return first[:REASON_MAX]
    frames = traceback.extract_tb(exc.__traceback__)
    if frames:
        last = frames[-1]
        where = f"{Path(last.filename).name}:{last.lineno}"
        code = (last.line or "").strip()
        return f"{type(exc).__name__} at {where}" + (f": {code}" if code else "")
    return f"{type(exc).__name__} (no message)"


def full_error(exc: BaseException) -> str:
    """The whole exception text (Playwright's expected/actual/call log)."""
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else \
        f"{type(exc).__name__} (no message)"


def safe_name(nodeid: str) -> str:
    """A file-name-safe form of a nodeid, shared by step files and traces."""
    safe = re.sub(r"[^\w.-]+", "_", nodeid).strip("_")
    if len(safe) > NAME_MAX:
        digest = hashlib.sha1(nodeid.encode()).hexdigest()[:8]
        safe = f"{safe[:NAME_MAX]}_{digest}"
    return safe


def _json_safe(value):
    return value if isinstance(value, (str, int, float, bool)) else None


class StepRecorder:
    def __init__(self, suite: str, nodeid: str):
        self.suite = suite
        self.nodeid = nodeid
        self._started = datetime.now(UTC)
        self.steps: list[dict] = []
        self.metadata: dict = {}
        self.status = "running"
        self._soft_failures: list[str] = []
        self._watchers: list = []
        self._pending: list[tuple[str, str, bytes]] = []
        # step number -> [(label, extension, content)], what each check saw
        self.attachments: dict[int, list[tuple[str, str, bytes]]] = {}

    # --- evidence --------------------------------------------------------------

    def attach(self, label: str, content, ext: str = "txt"):
        """Inside a check: keep what it saw (an email, a response, rows). It is
        written to the test's evidence folder only if that check fails."""
        data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        self._pending.append((label, ext.lstrip("."), data))

    # --- watchers ------------------------------------------------------------

    def watch(self, watcher):
        """Tell `watcher` about every step: watcher.started(name) before a step
        runs, watcher.finished(step, number) once it is recorded (number is its
        1-based position). Evidence collectors use this; they never change a
        test's outcome - a watcher that breaks is reported and ignored."""
        self._watchers.append(watcher)

    def _notify(self, event: str, *args):
        for watcher in self._watchers:
            try:
                getattr(watcher, event)(*args)
            except Exception as exc:
                print(f"[evidence] {type(watcher).__name__}.{event} failed: "
                      f"{type(exc).__name__}: {exc}")

    # --- recording -----------------------------------------------------------

    def _add(self, name: str, status: str, message: str, data: dict,
             expected: str = None, means: str = None, error: str = None,
             ui: bool = False) -> dict:
        step = {"step": name, "status": status, "message": message,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "data": {k: v for k, v in data.items() if v is not None}}
        for key, value in (("expected", expected), ("means", means), ("error", error)):
            if value:
                step[key] = value
        if ui:
            step["ui"] = True
        if self._pending:
            self.attachments[len(self.steps) + 1] = self._pending
            step["attachments"] = [f"{label}.{ext}" for label, ext, _ in self._pending]
            self._pending = []
        self.steps.append(step)
        print(f"[{status.upper()}] {name}: {message}")
        self._notify("finished", step, len(self.steps))
        return step

    def step(self, name: str, fn, expected: str = "", means: str = None, found=None,
             ui: bool = False, **data):
        """Run `fn`; on success record `expected` as the result text - or, when
        `found` is given, the sentence found(return value), for steps whose value is
        the point (a reading). On failure record the real exception as the reason
        and `expected` beside it. ui=True marks a check of what is on screen."""
        self._pending = []
        self._notify("started", name)
        try:
            out = fn()
            said = found(out) if found else expected
        except Exception as exc:
            self._add(name, FAILED, describe(exc), data, expected=expected,
                      means=means or classify(exc), error=full_error(exc), ui=ui)
            raise
        result = _json_safe(out)
        if result is not None:
            data = {**data, "result": result}
        self._add(name, PASSED, said, data, ui=ui)
        return out

    def soft_step(self, name: str, fn, expected: str = "", means: str = None, found=None,
                  ui: bool = False, **data):
        try:
            return self.step(name, fn, expected, means=means, found=found, ui=ui, **data)
        except Exception as exc:
            self._soft_failures.append(f"{name}: {describe(exc)}")
            return None

    def skip_step(self, name: str, reason: str, expected: str = "", **data):
        self._add(name, SKIPPED, reason, data, expected=expected)

    def known_issue(self, name: str, message: str, **data):
        self._add(name, KNOWN_ISSUE, message, data)

    def add_metadata(self, key: str, value):
        self.metadata[key] = value

    def raise_soft_failures(self):
        """Fail the test once, listing every independent check that failed."""
        if self._soft_failures:
            raise AssertionError(
                f"{len(self._soft_failures)} independent check(s) failed:\n- "
                + "\n- ".join(self._soft_failures))

    # --- outcome -------------------------------------------------------------

    def finalize(self, status: str):
        """'completed' becomes 'failed' if any step failed."""
        if status == "completed" and any(s["status"] == FAILED for s in self.steps):
            status = "failed"
        self.status = status

    def to_dict(self) -> dict:
        ended = datetime.now(UTC)
        return {"suite": self.suite, "nodeid": self.nodeid, "status": self.status,
                "started": self._started.isoformat(timespec="seconds"),
                "ended": ended.isoformat(timespec="seconds"),
                "duration": round((ended - self._started).total_seconds(), 2),
                "steps": self.steps, "metadata": self.metadata}

    def save(self, directory: Path) -> Path:
        """One file per test, named from its nodeid; the nodeid inside the file
        is what the report builder matches on."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"steps__{safe_name(self.nodeid)}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str),
                        encoding="utf-8")
        return path
