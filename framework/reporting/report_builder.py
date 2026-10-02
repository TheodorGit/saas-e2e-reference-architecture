"""Build a run's reports from its directory."""
import html
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from framework.reporting import evidence, profiles
from framework.reporting.failure_reasons import classify_failure_text, first_error_line
from framework.reporting.recorder import FAILED, KNOWN_ISSUE, PASSED, SKIPPED

INK, MUTED, LINE, PAGE, ACCENT = "#1F2937", "#6B7280", "#E5E7EB", "#F4F4F7", "#4F46E5"
STATUS = {
    "passed": {"fg": "#15803D", "bg": "#DCFCE7", "label": "PASSED"},
    "failed": {"fg": "#B91C1C", "bg": "#FEE2E2", "label": "FAILED"},
    "skipped": {"fg": "#B45309", "bg": "#FEF3C7", "label": "SKIPPED"},
    "known_issue": {"fg": "#B45309", "bg": "#FEF3C7", "label": "KNOWN ISSUE"},
}


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _duration(seconds) -> str:
    seconds = int(seconds or 0)
    return f"{seconds}s" if seconds < 60 else f"{seconds // 60}m {seconds % 60:02d}s"


def _when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return iso or ""


def _step_files(run_dir: Path) -> dict:
    by_nodeid = {}
    for path in sorted(run_dir.glob("steps__*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if data.get("nodeid"):
            by_nodeid[data["nodeid"]] = data
    return by_nodeid


def _evidence(run_dir: Path) -> dict:
    found = {}
    trace = evidence.TRACE_FILE
    for id_file in sorted((run_dir / evidence.EVIDENCE_DIR).glob(f"*/{evidence.ID_FILE}")):
        folder = id_file.parent
        nodeid = id_file.read_text(encoding="utf-8").splitlines()[0].strip()
        rel = f"{evidence.EVIDENCE_DIR}/{folder.name}"
        files: dict = {}
        for item in sorted(folder.iterdir()):
            number, _, rest = item.stem.partition(" ")
            if number.isdigit() and int(number) > 0:
                label = "Screen" if item.suffix == ".png" else f"{rest} ({item.suffix})"
                files.setdefault(int(number), []).append((label, f"{rel}/{item.name}"))
        found[nodeid] = {
            "folder": rel, "files": files,
            "trace": f"{rel}/{trace}" if (folder / trace).exists() else None}
    return found


def load_run(run_dir) -> dict:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"{manifest_path} not found: nothing authoritative "
                                f"to report on")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    steps_by_nodeid = _step_files(run_dir)
    evidence = _evidence(run_dir)

    tests = []
    for entry in manifest.get("tests", []):
        nodeid, func = entry["nodeid"], entry["func"]
        profile = profiles.profile_for(nodeid)
        steps = steps_by_nodeid.get(nodeid, {}).get("steps", [])
        tests.append({
            "nodeid": nodeid, "func": func, "profile": profile.key,
            "section": profile.section_for(func),
            "title": profile.title_for(func),
            "number": profile.number_for(func),
            "status": entry["status"], "duration": entry.get("duration", 0),
            "failure": entry.get("failure"), "skip_reason": entry.get("skip_reason"),
            "steps": steps,
            "known_issues": [s.get("message", "") for s in steps
                             if s.get("status") == KNOWN_ISSUE],
            "skipped_checks": [(s.get("step", ""), s.get("message", ""))
                               for s in steps if s.get("status") == SKIPPED],
            "metadata": steps_by_nodeid.get(nodeid, {}).get("metadata", {}),
            "evidence": evidence.get(nodeid),
        })
    tests.sort(key=lambda t: (t["number"] == 0, t["number"]))

    counts = {s: sum(1 for t in tests if t["status"] == s)
              for s in ("passed", "failed", "skipped")}
    counts["total"] = len(tests)
    counts["known_issues"] = sum(len(t["known_issues"]) for t in tests)
    counts["skipped_checks"] = sum(len(t["skipped_checks"]) for t in tests)
    # A test with no recorded steps still checked one thing directly.
    counts["checks"] = sum(len(t["steps"]) or 1 for t in tests) - counts["skipped_checks"]
    counts["checks_passed"] = sum(
        sum(1 for s in t["steps"] if s.get("status") == PASSED) if t["steps"]
        else int(t["status"] == "passed") for t in tests)
    # Steps for a test the manifest never saw: the counts understate the run.
    known = {t["nodeid"] for t in tests}
    counts["orphan_step_files"] = sorted(n for n in steps_by_nodeid if n not in known)
    verdict = ("failed" if counts["failed"] else
               "skipped" if counts["skipped"] else "passed")

    keys = {t["profile"] for t in tests}
    identity = next((p for p in profiles.registered() if {p.key} == keys),
                    profiles.GENERIC)
    facts = identity.facts(run_dir, tests) if identity.facts else []

    return {
        "run_id": manifest.get("run_id"), "started": manifest.get("started"),
        "finished": manifest.get("finished"), "duration": manifest.get("duration", 0),
        "environment": manifest.get("environment"),
        "interrupted": manifest.get("interrupted", False),
        "suite": identity.key, "suite_title": identity.title,
        "passed_subhead": identity.passed_subhead,
        "counts": counts, "verdict": verdict, "facts": facts, "tests": tests,
        "subject": subject_line(identity.title, verdict, counts,
                                manifest.get("finished")),
    }


def subject_line(name: str, verdict: str, counts: dict, finished: str) -> str:
    total = counts["total"]
    if verdict == "failed":
        head = f"[FAILED] {name}: {counts['failed']} of {total} tests failed"
    elif verdict == "skipped":
        head = f"[GAPS] {name}: {counts['passed']} passed, {counts['skipped']} not verified"
    else:
        head = f"[PASSED] {name}: all {total} tests passed"
    head += f" - {counts['checks_passed']} of {counts['checks']} checks passed"
    if counts.get("known_issues"):
        head += f" ({counts['known_issues']} known issue(s))"
    if counts.get("skipped_checks"):
        head += f" ({counts['skipped_checks']} check(s) not run)"
    return head + (f" - {_when(finished)}" if finished else "")


def failure_view(test: dict) -> dict:
    bad = next((s for s in test["steps"] if s.get("status") == FAILED), None)
    if bad:
        return {"step": bad.get("step", ""), "means": (bad.get("means") or "").strip(),
                "expected": (bad.get("expected") or "").strip(),
                "instead": (bad.get("message") or "").strip()
                or first_error_line(test["failure"]),
                "error": (bad.get("error") or "").strip()}
    return {"step": "", "means": classify_failure_text(test["failure"]),
            "expected": "", "instead": first_error_line(test["failure"]), "error": ""}


def _pill(status: str) -> str:
    s = STATUS.get(status, STATUS["skipped"])
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            f'background:{s["bg"]};color:{s["fg"]};font-size:11px;font-weight:700;'
            f'letter-spacing:.04em;">{s["label"]}</span>')


def _labelled(label: str, value: str) -> str:
    return (f'<div style="margin-top:6px;font-size:13px;color:{INK};">'
            f'<span style="color:{MUTED};font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.05em;">{label}</span> {_esc(value)}</div>')


def _why_box(means: str, expected: str, instead: str, detail: str) -> str:
    s = STATUS["failed"]
    head = (f'<div style="font-weight:600;font-size:14px;">{_esc(means)}</div>'
            if means else "")
    if expected:
        head += _labelled("Expected", expected)
    head += _labelled("Instead", instead)
    full = (f'<details style="margin-top:10px;"><summary style="cursor:pointer;'
            f'font-size:12px;color:{MUTED};">Full error</summary>'
            f'<pre style="white-space:pre-wrap;word-break:break-word;font-size:12px;'
            f'margin:8px 0 0;">{_esc(detail)}</pre></details>') if detail else ""
    return (f'<div style="margin:8px 0 2px;padding:12px;background:{s["bg"]};'
            f'border-radius:4px;"><div style="color:{s["fg"]};font-weight:700;'
            f'font-size:12px;margin-bottom:6px;">WHY IT FAILED</div>{head}{full}</div>')


def _note_box(title: str, text: str, status: str) -> str:
    s = STATUS[status]
    return (f'<div style="margin:8px 0 2px;padding:10px;background:{s["bg"]};'
            f'border-radius:4px;font-size:13px;"><b style="color:{s["fg"]};">{title}</b> '
            f'{_esc(text)}</div>')


def _steps_table(test: dict) -> str:
    if not test["steps"]:
        text = {"passed": "No steps recorded: this test asserts directly.",
                "skipped": "No steps recorded: skipped before its first step.",
                }.get(test["status"], "No steps recorded: it failed before its first step.")
        return f'<p style="color:{MUTED};font-size:13px;">{text}</p>'
    rows, first_failure = [], True
    files = (test.get("evidence") or {}).get("files", {})
    for number, step in enumerate(test["steps"], 1):
        status = step.get("status", SKIPPED)
        cell = ""
        if status == FAILED:
            detail = (step.get("error") or "").strip()
            if first_failure and test["failure"]:
                # The test's own failure output belongs to the check that broke first.
                detail = f"{detail}\n\n{test['failure']}".strip()
            first_failure = False
            cell += _why_box((step.get("means") or "").strip(),
                             (step.get("expected") or "").strip(),
                             (step.get("message") or "").strip(), detail)
        elif status == KNOWN_ISSUE:
            cell += _note_box("Known issue:", step.get("message"), "known_issue")
        elif status == SKIPPED:
            cell += _note_box("Not run:", step.get("message"), "skipped")
            if step.get("expected"):
                cell += _labelled("Would have checked", step["expected"])
        else:
            cell += f'<div style="font-size:13px;">{_esc(step.get("message"))}</div>'
        if number in files:
            links = " - ".join(f'<a href="{_esc(quote(path))}">{_esc(label)}</a>'
                               for label, path in files[number])
            cell += (f'<div style="margin-top:4px;font-size:12px;color:{MUTED};">'
                     f'Evidence: {links}</div>')
        td = f'padding:8px;border-bottom:1px solid {LINE};vertical-align:top;'
        rows.append(
            f'<tr><td style="{td}white-space:nowrap;width:1%;">{_pill(status)}</td>'
            f'<td style="{td}width:34%;font-size:13px;">{_esc(step.get("step"))}</td>'
            f'<td style="{td}">{cell}</td></tr>')
    th = (f'padding:6px 8px;border-bottom:2px solid {LINE};text-align:left;font-size:11px;'
          f'color:{MUTED};text-transform:uppercase;letter-spacing:.05em;font-weight:600;')
    head = (f'<thead><tr><th style="{th}"></th><th style="{th}">Check</th>'
            f'<th style="{th}">Result</th></tr></thead>')
    return (f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
            f'{head}<tbody>{"".join(rows)}</tbody></table>')


def _test_block(test: dict) -> str:
    status = test["status"]
    opened = " open" if (status != "passed" or test["known_issues"]
                         or test["skipped_checks"]) else ""
    body = ""
    if status == "skipped" and test["skip_reason"]:
        body += _note_box("Skipped:", test["skip_reason"], "skipped")
    elif status == "failed" and test["failure"] and not any(
            s.get("status") == FAILED for s in test["steps"]):
        f = failure_view(test)
        body += _why_box(f["means"], f["expected"], f["instead"], test["failure"])
    video = (test.get("metadata") or {}).get("video")
    if video:
        body += (f'<div style="margin:6px 0;font-size:12px;color:{MUTED};">'
                 f'<a href="{_esc(quote(video))}">Watch this test</a> - a video of what '
                 f'the browser did.</div>')
    kept = test.get("evidence")
    if kept:
        trace = (f' Also: <a href="{_esc(quote(kept["trace"]))}">the trace</a> '
                 f'(open with playwright show-trace).' if kept["trace"] else "")
        body += (f'<div style="margin:6px 0;font-size:12px;color:{MUTED};">Evidence folder: '
                 f'<a href="{_esc(quote(kept["folder"]))}/">{_esc(kept["folder"])}/</a> - '
                 f'files are numbered by the check they belong to, listed in test.txt.'
                 f'{trace}</div>')
    steps = test["steps"]
    passed = sum(1 for st in steps if st.get("status") == PASSED)
    count = f"{passed}/{len(steps)} steps" if steps else "no steps"
    number = f'<b style="color:{MUTED};">#{test["number"]}</b> ' if test["number"] else ""
    return (f'<details{opened} style="border:1px solid {LINE};border-radius:6px;'
            f'margin-bottom:8px;background:#fff;"><summary style="padding:10px 12px;'
            f'cursor:pointer;">{_pill(status)} {number}<b>{_esc(test["title"])}</b> '
            f'<span style="color:{MUTED};font-size:12px;">- {count} - '
            f'{_duration(test["duration"])}</span></summary>'
            f'<div style="padding:0 12px 12px;"><div style="font-family:Consolas,'
            f'monospace;font-size:11px;color:{MUTED};">{_esc(test["nodeid"])}</div>'
            f'{body}{_steps_table(test)}</div></details>')


def _facts_table(facts: list) -> str:
    if not facts:
        return ""
    cells = "".join(
        f'<td style="padding:10px 14px;text-align:center;border-right:1px solid {LINE};">'
        f'<div style="font-size:20px;font-weight:700;">{_esc(v)}</div>'
        f'<div style="font-size:11px;color:{MUTED};text-transform:uppercase;">'
        f'{_esc(k)}</div></td>' for k, v in facts)
    return (f'<h2 style="font-size:13px;color:{MUTED};text-transform:uppercase;">'
            f'What this run actually did</h2><table style="border:1px solid {LINE};'
            f'background:#fff;border-collapse:collapse;"><tr>{cells}</tr></table>')


def _headline(run: dict) -> str:
    c = run["counts"]
    return {"failed": f'{c["failed"]} of {c["total"]} tests failed',
            "skipped": f'{c["passed"]} tests passed, {c["skipped"]} not verified',
            "passed": f'All {c["total"]} tests passed'}[run["verdict"]] \
        + f' - {c["checks"]} checks'


def render_report(run: dict) -> str:
    v = STATUS[run["verdict"]]
    c = run["counts"]
    sections, seen = [], []
    for test in run["tests"]:
        if test["section"] not in seen:
            seen.append(test["section"])
    for name in sorted(seen, key=lambda n: n == "Other"):
        blocks = "".join(_test_block(t) for t in run["tests"] if t["section"] == name)
        sections.append(f'<h2 style="font-size:13px;color:{MUTED};text-transform:'
                        f'uppercase;margin:24px 0 8px;">{_esc(name)}</h2>{blocks}')
    orphan = ""
    if c["orphan_step_files"]:
        orphan = (f'<p style="color:{STATUS["failed"]["fg"]};">Report integrity: '
                  f'steps were recorded for tests missing from the manifest, so the '
                  f'check count understates the run: {_esc(", ".join(c["orphan_step_files"]))}'
                  f'</p>')
    interrupted = (f'<p style="color:{STATUS["failed"]["fg"]};">This run was '
                   f'interrupted; tests still executing are reported as not verified.</p>'
                   if run["interrupted"] else "")
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>'
        f'{_esc(run["suite_title"])} {_esc(run["run_id"])}</title></head>'
        f'<body style="margin:0;background:{PAGE};font-family:-apple-system,Segoe UI,'
        f'Roboto,Arial,sans-serif;color:{INK};"><div style="max-width:960px;margin:0 auto;'
        f'padding:24px;"><div style="border-bottom:2px solid {ACCENT};padding-bottom:10px;'
        f'margin-bottom:16px;font-size:13px;color:{MUTED};"><b style="color:{INK};'
        f'font-size:16px;">{_esc(run["suite_title"])}</b> - run {_esc(run["run_id"])} - '
        f'{_esc(_when(run["finished"]))} - {_duration(run["duration"])}</div>'
        f'<div style="background:{v["bg"]};border-radius:8px;padding:16px 18px;">'
        f'<div style="color:{v["fg"]};font-weight:700;font-size:11px;letter-spacing:.08em;">'
        f'{v["label"]}</div><div style="font-size:22px;font-weight:700;">'
        f'{_esc(_headline(run))}</div><div style="font-size:13px;color:{MUTED};">'
        f'{c["passed"]} passed - {c["failed"]} failed - {c["skipped"]} skipped - '
        f'{c["known_issues"]} known issue(s) - {c["skipped_checks"]} check(s) not run'
        f'{" - environment " + _esc(run["environment"]) if run["environment"] else ""}'
        f'</div></div>{interrupted}{orphan}{"".join(sections)}{_facts_table(run["facts"])}'
        f'</div></body></html>')


def _email_card(test: dict, bg: str, inner: str) -> str:
    return (f'<tr><td style="padding:6px 24px;"><table width="100%" cellpadding="0" '
            f'cellspacing="0" style="background:{bg};border-radius:4px;"><tr><td '
            f'style="padding:12px 14px;"><div style="font-size:15px;font-weight:600;">'
            f'{_esc(test["title"])}</div>{inner}</td></tr></table></td></tr>')


def _email_heading(text: str, color: str) -> str:
    return (f'<tr><td style="padding:18px 24px 4px;font-size:12px;font-weight:700;'
            f'letter-spacing:.08em;text-transform:uppercase;color:{color};">'
            f'{_esc(text)}</td></tr>')


def render_email(run: dict) -> str:
    v = STATUS[run["verdict"]]
    by = lambda s: [t for t in run["tests"] if t["status"] == s]  # noqa: E731
    subhead = {"failed": "Failures first, each with the exact step that broke.",
               "skipped": "Nothing failed, but the tests below did not run.",
               "passed": run["passed_subhead"]}[run["verdict"]]
    blocks = []
    if by("failed"):
        blocks.append(_email_heading(f"Failed ({len(by('failed'))})", STATUS["failed"]["fg"]))
        for test in by("failed"):
            f = failure_view(test)
            inner = (f'<div style="margin-top:8px;font-size:14px;">{_esc(f["means"])}</div>'
                     if f["means"] else "")
            if f["expected"]:
                inner += _labelled("Expected", f["expected"])
            inner += _labelled("Instead", f["instead"])
            if f["step"]:
                inner += _labelled("Step", f["step"])
            blocks.append(_email_card(test, STATUS["failed"]["bg"], inner))
    known = [t for t in run["tests"] if t["known_issues"]]
    if known:
        blocks.append(_email_heading("Known issues", STATUS["known_issue"]["fg"]))
        for test in known:
            inner = "".join(f'<div style="margin-top:6px;font-size:13px;">{_esc(n)}</div>'
                            for n in test["known_issues"])
            blocks.append(_email_card(test, STATUS["known_issue"]["bg"], inner))
    not_run = [t for t in run["tests"] if t["skipped_checks"]]
    if not_run:
        blocks.append(_email_heading("Checks not run", STATUS["skipped"]["fg"]))
        for test in not_run:
            inner = "".join(f'<div style="margin-top:6px;font-size:13px;"><b>'
                            f'{_esc(n)}</b> - {_esc(r)}</div>'
                            for n, r in test["skipped_checks"])
            blocks.append(_email_card(test, STATUS["skipped"]["bg"], inner))
    if by("skipped"):
        blocks.append(_email_heading(f"Not verified ({len(by('skipped'))})",
                                     STATUS["skipped"]["fg"]))
        for test in by("skipped"):
            inner = (f'<div style="margin-top:6px;font-size:13px;">'
                     f'{_esc(test["skip_reason"] or "Skipped")}</div>')
            blocks.append(_email_card(test, STATUS["skipped"]["bg"], inner))
    if by("passed"):
        blocks.append(_email_heading(f"Passed ({len(by('passed'))})", STATUS["passed"]["fg"]))
        rows = "".join(f'<div style="padding:5px 0;font-size:14px;border-bottom:1px solid '
                       f'{LINE};">&#10003; {_esc(t["title"])}</div>' for t in by("passed"))
        blocks.append(f'<tr><td style="padding:2px 24px;">{rows}</td></tr>')
    strip = "".join(f'<td align="center" style="padding:10px 6px;"><div style="font-size:'
                    f'18px;font-weight:700;">{_esc(val)}</div><div style="font-size:10px;'
                    f'color:{MUTED};text-transform:uppercase;">{_esc(k)}</div></td>'
                    for k, val in run["facts"])
    strip_row = (f'<tr><td style="padding:0 24px;"><table width="100%" cellpadding="0" '
                 f'cellspacing="0"><tr>{strip}</tr></table></td></tr>') if strip else ""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE};'
        f'font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:{INK};">'
        f'<tr><td align="center" style="padding:20px 10px;"><table width="640" '
        f'cellpadding="0" cellspacing="0" style="width:640px;max-width:100%;background:'
        f'#fff;border:1px solid {LINE};border-radius:8px;">'
        f'<tr><td style="padding:18px 24px;border-bottom:3px solid {ACCENT};font-size:16px;'
        f'font-weight:700;">{_esc(run["suite_title"])}</td></tr>'
        f'<tr><td style="padding:16px 24px;background:{v["bg"]};"><div style="color:'
        f'{v["fg"]};font-size:11px;font-weight:700;letter-spacing:.08em;">{v["label"]}</div>'
        f'<div style="font-size:20px;font-weight:700;">{_esc(_headline(run))}</div>'
        f'<div style="font-size:13px;color:{MUTED};">{_esc(subhead)}</div></td></tr>'
        f'{strip_row}{"".join(blocks)}'
        f'<tr><td style="padding:16px 24px;background:{PAGE};font-size:12px;color:{MUTED};">'
        f'Run {_esc(run["run_id"])} - {_esc(_when(run["finished"]))} - '
        f'{_duration(run["duration"])}. The attached report has every step.</td></tr>'
        f'</table></td></tr></table>')


def write_latest(report: Path, page: Path) -> Path:
    page = Path(page)
    page.parent.mkdir(parents=True, exist_ok=True)
    target = _esc(quote(Path(os.path.relpath(report, page.parent)).as_posix()))
    page.write_text(
        f'<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        f'<title>Latest report</title></head><body style="font-family:-apple-system,'
        f'Segoe UI,Roboto,Arial,sans-serif;"><p>Opening the latest report: '
        f'<a href="{target}">{target}</a></p></body></html>', encoding="utf-8")
    return page


def build(run_dir) -> dict:
    run_dir = Path(run_dir)
    run = load_run(run_dir)
    summary = {k: v for k, v in run.items() if k != "tests"}
    summary["tests"] = [{k: t[k] for k in ("nodeid", "title", "status")}
                        for t in run["tests"]]
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                          encoding="utf-8")
    (run_dir / "report.html").write_text(render_report(run), encoding="utf-8")
    (run_dir / "email.html").write_text(render_email(run), encoding="utf-8")
    return {"verdict": run["verdict"], "subject": run["subject"],
            "report": run_dir / "report.html", "email": run_dir / "email.html",
            "summary": run_dir / "summary.json"}
