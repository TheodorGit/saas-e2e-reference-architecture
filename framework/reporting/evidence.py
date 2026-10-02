"""A failed test's evidence folder and its file names."""
import re
from pathlib import Path

from framework import tokens
from framework.reporting import profiles
from framework.reporting.recorder import FAILED, SKIPPED, StepRecorder, safe_name

EVIDENCE_DIR = "evidence"
ID_FILE = "test.txt"
TRACE_FILE = "00 trace.zip"
LABEL_MAX = 50
_UNSAFE = re.compile(r'[<>:"/\|?*\x00-\x1f]+')


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", _UNSAFE.sub("_", text or "")).strip(" ._")


def middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head, tail = limit // 2, (limit - 1) // 2
    return f"{text[:head].rstrip()}~{text[len(text) - tail:].lstrip()}"


def check_file(number: int, label: str = "screen", ext: str = "png") -> str:
    return f"{number:02d} {middle(clean(tokens.shorten(label)), LABEL_MAX) or 'file'}.{ext}"


def folder_name(recorder: StepRecorder) -> str:
    return safe_name(recorder.nodeid.split("::")[-1].split("[")[0])


def title_of(recorder: StepRecorder) -> str:
    func = recorder.nodeid.split("::")[-1].split("[")[0]
    return profiles.profile_for(recorder.nodeid).title_for(func)


def write_index(recorder: StepRecorder, folder: Path):
    # The report matches on the first line, the nodeid.
    lines = [recorder.nodeid, title_of(recorder)]
    for number, step in enumerate(recorder.steps, 1):
        result = (step.get("status") or SKIPPED).upper().replace("_", " ")
        lines.append(f"{number:02d}  {result}  {step.get('step', '')}")
    (folder / ID_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def folder_for(recorder: StepRecorder, run_dir: Path) -> Path:
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
