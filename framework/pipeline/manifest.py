"""The run manifest: which tests ran and how each ended, and what was selected."""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

SELECTION_FILE = "selection.json"


class RunManifest:
    def __init__(self, run_id: str, environment: str | None = None):
        self.run_id = run_id
        self.environment = environment
        self.started = datetime.now(UTC)
        self.tests = {}

    def record(self, report, func: str) -> dict:
        entry = self.tests.setdefault(report.nodeid, {
            "nodeid": report.nodeid,
            "func": func,
            "status": "passed",
            "duration": 0.0,
            "failure": None,
            "skip_reason": None,
        })
        entry["duration"] += report.duration
        entry["last_phase"] = report.when
        if report.failed and entry["status"] != "failed":
            entry["status"] = "failed"
            entry["failure"] = (getattr(report, "longreprtext", "")
                                or str(report.longrepr)).strip()
        elif report.skipped and entry["status"] == "passed":
            entry["status"] = "skipped"
            entry["skip_reason"] = skip_reason(report)
        return entry

    def snapshot(self, final: bool) -> dict:
        now = datetime.now(UTC)
        tests = []
        for entry in self.tests.values():
            entry = dict(entry)
            in_flight = entry.pop("last_phase", None) != "teardown"
            if in_flight and entry["status"] == "passed":
                entry["status"] = "skipped"
                entry["skip_reason"] = "run interrupted while this test was executing"
            tests.append(entry)
        return {
            "run_id": self.run_id,
            "started": self.started.isoformat(timespec="seconds"),
            "finished": now.isoformat(timespec="seconds"),
            "duration": round((now - self.started).total_seconds(), 1),
            "environment": self.environment,
            "interrupted": not final,
            "tests": tests,
        }

    def write(self, directory: Path, final: bool) -> Path:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(self.snapshot(final), indent=2), encoding="utf-8")
        return path


def record_selection(directory, collected: int, selected: int,
                     expression: str = "") -> Path:
    path = Path(directory) / SELECTION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(f".{os.getpid()}.json")
    partial.write_text(json.dumps({
        "collected": collected,
        "selected": selected,
        "deselected": collected - selected,
        "expression": expression or "",
    }, indent=2), encoding="utf-8")
    # Replaced in one step: the report is built from whatever is on disk, and a run
    # killed mid-write must not leave half a file behind.
    os.replace(partial, path)
    return path


def read_selection(directory) -> dict:
    path = Path(directory) / SELECTION_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def skip_reason(report) -> str:
    longrepr = getattr(report, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2]).removeprefix("Skipped: ")
    return ""
