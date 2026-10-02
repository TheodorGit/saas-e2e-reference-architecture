"""The run manifest: which tests ran and how each ended."""
import json
from datetime import UTC, datetime
from pathlib import Path


class RunManifest:
    def __init__(self, run_id: str, environment: str = None):
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


def skip_reason(report) -> str:
    longrepr = getattr(report, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2]).removeprefix("Skipped: ")
    return ""
