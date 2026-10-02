"""Run ids, subject tokens and entity names.

Every run gets one id. Everything the run creates or sends carries a token built
from it, so a search for the token can only ever find this run's work: never an
earlier run's, never another test's, never a leftover.
"""
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

_RUN_ID = None


def new_run_id(now: datetime = None) -> str:
    """'0930_1412a3f9': readable time first, random suffix for same-minute runs."""
    return f"{(now or datetime.now()):%m%d_%H%M}{uuid.uuid4().hex[:4]}"


def current_run_id() -> str:
    """This process's run id, created once. Hooks and fixtures share it."""
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = new_run_id()
    return _RUN_ID


def prefix() -> str:
    """Prefix on every created entity, so leftovers are recognisable."""
    return os.getenv("E2E_NAME_PREFIX", "QA")


def subject_token(run_id: str, slug: str) -> str:
    """Unique, searchable token for an email subject."""
    return f"{prefix()}-{run_id}-{slug}-{uuid.uuid4().hex[:8]}"


def entity_name(run_id: str, slug: str) -> str:
    """Unique, prefixed name for an entity the run creates."""
    return f"{prefix()}-{run_id}-{slug}-{uuid.uuid4().hex[:6]}"


def shorten(text: str) -> str:
    """Each token in `text`, or an address carrying one, cut to its slug: for names
    that already sit inside the run's own folder, where the rest is noise."""
    token = re.compile(
        rf"(?:[\w.-]+\+)?{re.escape(prefix())}-\d{{4}}_\d{{4}}[0-9a-f]{{4}}-"
        rf"(?P<slug>[\w-]+?)-[0-9a-f]{{6}}(?:[0-9a-f]{{2}})?(?![0-9a-z])(?:@[\w.-]+)?",
        re.IGNORECASE)
    return token.sub(lambda m: m.group("slug"), text or "")


RUN_ID_PATTERN = r"\d{4}_\d{4}[0-9a-f]{4}"


def results_root() -> Path:
    return Path(os.getenv("E2E_RESULTS_DIR", "reports"))


def run_label() -> str:
    """What this run is, for its folder name (E2E_RUN_LABEL: 'clean', a defect)."""
    return re.sub(r'[<>:"/\\|?*\s]+', "_", os.getenv("E2E_RUN_LABEL", "")).strip("_.")


def run_dir() -> Path:
    """This run's artifact directory, '<run id>-<label>'; created on first use."""
    label = run_label()
    path = results_root() / (f"{current_run_id()}-{label}" if label else current_run_id())
    path.mkdir(parents=True, exist_ok=True)
    return path


def newest_run(root: Path, label: str, marker: str = "manifest.json") -> Path | None:
    """The newest finished run under `root` with exactly this label: finished means
    it holds `marker`, and the newest is the one whose marker was written last."""
    name = re.compile(rf"{RUN_ID_PATTERN}-{re.escape(label)}")
    root = Path(root)
    runs = [p for p in (root.iterdir() if root.is_dir() else [])
            if p.is_dir() and name.fullmatch(p.name) and (p / marker).exists()]
    return max(runs, key=lambda p: (p / marker).stat().st_mtime, default=None)
