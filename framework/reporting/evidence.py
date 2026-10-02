"""A failed test's evidence: one folder, named after the test, holding what each
failed check saw - of the kind that check was about.

    evidence/test_send_to_a_segment/
        test.txt                         the test, then every check: number, result, check
        06 the email they received.html
        06 the email they received.eml
        06 the email they received - headers.txt

Files are numbered by the check they belong to and named for what they are. The
check itself, and whether it failed, is in test.txt beside its number - never in a
file name - so names stay short and a report's paths fit Windows. A run token in a
label is cut to its slug (the folder already says which run). An inbox check keeps
the email, an API check the request and response, a reconciliation the rows it
read; a screen check keeps its screen (framework/ui/tracing.py adds those, with the
trace and a video). A passing test keeps nothing.
"""
import re
from pathlib import Path

from framework import tokens
from framework.reporting import profiles
from framework.reporting.recorder import FAILED, SKIPPED, StepRecorder, safe_name

EVIDENCE_DIR = "evidence"
ID_FILE = "test.txt"
TRACE_FILE = "00 trace.zip"
LABEL_MAX = 50   # labels are short phrases a test names; this only stops a careless one
_UNSAFE = re.compile(r'[<>:"/\|?*\x00-\x1f]+')


def clean(text: str) -> str:
    """Text safe in a file name on every platform; spaces kept for reading."""
    return re.sub(r"\s+", " ", _UNSAFE.sub("_", text or "")).strip(" ._")


def middle(text: str, limit: int) -> str:
    """`text` cut to `limit` in the middle, so both its ends survive."""
    if len(text) <= limit:
        return text
    head, tail = limit // 2, (limit - 1) // 2
    return f"{text[:head].rstrip()}~{text[len(text) - tail:].lstrip()}"


def check_file(number: int, label: str = "screen", ext: str = "png") -> str:
    """'06 the email they received.html'; a check's screen is '04 screen.png'."""
    return f"{number:02d} {middle(clean(tokens.shorten(label)), LABEL_MAX) or 'file'}.{ext}"


def folder_name(recorder: StepRecorder) -> str:
    """The test's function name, without parameters: 'test_send', not
    'test_send[chromium]'. Folders and videos are named by it."""
    return safe_name(recorder.nodeid.split("::")[-1].split("[")[0])


def title_of(recorder: StepRecorder) -> str:
    func = recorder.nodeid.split("::")[-1].split("[")[0]
    return profiles.profile_for(recorder.nodeid).title_for(func)


def write_index(recorder: StepRecorder, folder: Path):
    """test.txt: the test's nodeid (what the report matches on), its title, then
    every check with its number and result."""
    lines = [recorder.nodeid, title_of(recorder)]
    for number, step in enumerate(recorder.steps, 1):
        result = (step.get("status") or SKIPPED).upper().replace("_", " ")
        lines.append(f"{number:02d}  {result}  {step.get('step', '')}")
    (folder / ID_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def folder_for(recorder: StepRecorder, run_dir: Path) -> Path:
    """This test's evidence folder, created once. Two tests sharing a name get
    two folders; each says whose it is in test.txt."""
    existing = getattr(recorder, "_evidence_folder", None)
    if existing is not None:
        return existing
    root = Path(run_dir) / EVIDENCE_DIR
    base = folder_name(recorder)
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base}_{n}", n + 1
    folder.mkdir(parents=True)
    write_index(recorder, folder)
    recorder._evidence_folder = folder
    return folder


def save_attachments(recorder: StepRecorder, run_dir: Path) -> list[Path]:
    """Write what each FAILED check attached; a passing check's are dropped. Called
    once the test has ended, so test.txt is refreshed with every check."""
    written = []
    for number, items in sorted(recorder.attachments.items()):
        if recorder.steps[number - 1].get("status") != FAILED:
            continue
        folder = folder_for(recorder, run_dir)
        for label, ext, content in items:
            path = folder / check_file(number, label, ext)
            path.write_bytes(content)
            written.append(path)
    folder = getattr(recorder, "_evidence_folder", None)
    if folder is not None:
        write_index(recorder, folder)
    return written
