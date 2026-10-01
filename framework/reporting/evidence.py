"""A failed test's evidence: one folder, named after the test, holding what each
failed check saw - of the kind that check was about.

    evidence/test_send_to_a_segment_chromium/
        06_check failed - nobody else got it - the email they received.html
        06_check failed - nobody else got it - the email they received.eml
        test.txt                      the test's nodeid and title

Files are numbered by the check's position in the test and named after it; a
failed check says "check failed - <check>", so a check named for what should be
true cannot be read backwards. A run token in a name is cut to its slug (the folder
already says which run), and a name stays within FILE_MAX characters, shortened in
the middle if it must be, so a report's paths fit Windows. An inbox check keeps the
email, an API check the request and response, a reconciliation the rows it read; a
screen check keeps its screen (framework/ui/tracing.py adds those, with the trace
and a video). A passing test keeps nothing.
"""
import re
from pathlib import Path

from framework import tokens
from framework.reporting import profiles
from framework.reporting.recorder import FAILED, StepRecorder, safe_name

EVIDENCE_DIR = "evidence"
ID_FILE = "test.txt"
FILE_MAX = 100   # a whole evidence file name: keeps a report's paths inside Windows' 260
LABEL_MAX = 40
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def clean(text: str) -> str:
    """Text safe in a file name on every platform; spaces kept for reading."""
    return re.sub(r"\s+", " ", _UNSAFE.sub("_", text or "")).strip(" ._")


def middle(text: str, limit: int) -> str:
    """`text` cut to `limit` in the middle, so both its ends survive."""
    if len(text) <= limit:
        return text
    head, tail = limit // 2, (limit - 1) // 2
    return f"{text[:head].rstrip()}~{text[len(text) - tail:].lstrip()}"


def check_file(number: int, step: dict, label: str = "", ext: str = "png") -> str:
    """'06_check failed - nobody else got it - the email.html', or
    '04_the list shows it sent.png' for a check that passed."""
    failed = "check failed - " if step.get("status") == FAILED else ""
    tail = f" - {middle(clean(tokens.shorten(label)), LABEL_MAX)}" if label else ""
    room = max(10, FILE_MAX - len(f"{number:02d}_{failed}{tail}.{ext}"))
    name = middle(clean(tokens.shorten(step.get("step") or "check")), room)
    return f"{number:02d}_{failed}{name}{tail}.{ext}"


def title_of(recorder: StepRecorder) -> str:
    func = recorder.nodeid.split("::")[-1].split("[")[0]
    return profiles.profile_for(recorder.nodeid).title_for(func)


def folder_for(recorder: StepRecorder, run_dir: Path) -> Path:
    """This test's evidence folder, created once. Two tests sharing a name get
    two folders; each says whose it is in test.txt."""
    existing = getattr(recorder, "_evidence_folder", None)
    if existing is not None:
        return existing
    root = Path(run_dir) / EVIDENCE_DIR
    base = safe_name(recorder.nodeid.split("::")[-1])
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base}_{n}", n + 1
    folder.mkdir(parents=True)
    (folder / ID_FILE).write_text(f"{recorder.nodeid}\n{title_of(recorder)}\n",
                                  encoding="utf-8")
    recorder._evidence_folder = folder
    return folder


def save_attachments(recorder: StepRecorder, run_dir: Path) -> list[Path]:
    """Write what each FAILED check attached; a passing check's are dropped."""
    written = []
    for number, items in sorted(recorder.attachments.items()):
        step = recorder.steps[number - 1]
        if step.get("status") != FAILED:
            continue
        folder = folder_for(recorder, run_dir)
        for label, ext, content in items:
            path = folder / check_file(number, step, label, ext)
            path.write_bytes(content)
            written.append(path)
    return written
