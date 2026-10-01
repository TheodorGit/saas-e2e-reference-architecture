"""Build the sample-report site: a green run and a red run, as GitHub Pages serves them.

    python scripts/build_site.py --green reports/clean --red reports/suppression_leak --out site

Each source is a results root; its newest finished run_* is copied whole, so every link
inside the report (videos, evidence, the mailed email) keeps working. index.html is a
landing page with one card per run. CI builds and deploys it on every push to main.
"""
import argparse
import html
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from example.app.bugs import FLAGS  # noqa: E402
from framework.reporting.report_builder import (  # noqa: E402
    ACCENT,
    INK,
    LINE,
    MUTED,
    PAGE,
    STATUS,
)

SOURCE_NOTE = "Built by CI from the latest push to main."


def long_path(path: Path) -> str:
    """Windows refuses paths over 260 characters unless they carry the \\\\?\\ prefix,
    and evidence file names in a report can be long."""
    full = str(path.resolve())
    return "\\\\?\\" + full if os.name == "nt" and not full.startswith("\\\\?\\") else full


def newest_run(root: Path) -> Path:
    runs = sorted((p for p in root.glob("run_*") if (p / "summary.json").exists()),
                  key=lambda p: (p / "summary.json").stat().st_mtime)
    if not runs:
        sys.exit(f"no finished run with a report under {root}")
    return runs[-1]


def _when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return iso or ""


def _headline(summary: dict) -> str:
    c = summary["counts"]
    if summary["verdict"] == "passed":
        return f"All {c['total']} tests passed - {c['checks']} checks"
    return f"{c['failed']} of {c['total']} tests failed - {c['checks']} checks"


def card(folder: str, summary: dict, title: str, text: str) -> str:
    s = STATUS.get(summary["verdict"], STATUS["skipped"])
    esc = html.escape
    return (
        f'<section style="flex:1 1 300px;background:#fff;border:1px solid {LINE};'
        f'border-radius:8px;overflow:hidden;">'
        f'<div style="background:{s["bg"]};padding:14px 16px;"><div style="color:{s["fg"]};'
        f'font-weight:700;font-size:11px;letter-spacing:.08em;">{s["label"]}</div>'
        f'<div style="font-size:19px;font-weight:700;">{esc(_headline(summary))}</div></div>'
        f'<div style="padding:14px 16px;"><h2 style="font-size:15px;margin:0 0 6px;">'
        f'{esc(title)}</h2><p style="margin:0 0 12px;font-size:14px;">{esc(text)}</p>'
        f'<p style="margin:0 0 12px;font-size:12px;color:{MUTED};">Run {esc(summary["run_id"])}'
        f' - {esc(_when(summary.get("finished")))}</p>'
        f'<a href="{folder}/report.html" style="display:inline-block;background:{ACCENT};'
        f'color:#fff;text-decoration:none;padding:8px 14px;border-radius:6px;'
        f'font-weight:600;">Open the report</a></div></section>')


def landing(green: dict, red: dict, flag: str) -> str:
    repo = os.getenv("GITHUB_REPOSITORY")
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    source = (f' Source: <a href="{server}/{html.escape(repo)}">{html.escape(repo)}</a>.'
              if repo else "")
    cards = (
        card("green", green, "A clean run",
             "Every action is reconciled on a surface independent of the one that drove "
             "it: the inbox, the billing journal, the reports, the API and the dashboard.")
        + card("red", red, f"A defect switched on: {flag}",
               f"The app is broken on purpose ({FLAGS.get(flag, flag)}). The test that "
               "guards it fails at the exact check and keeps what that check saw, and "
               "every other surface the defect reaches says so too."))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Sample reports - saas-e2e-reference-architecture</title></head>'
        f'<body style="margin:0;background:{PAGE};color:{INK};font-family:-apple-system,'
        'Segoe UI,Roboto,Arial,sans-serif;"><main style="max-width:960px;margin:0 auto;'
        'padding:24px 16px;">'
        f'<div style="border-bottom:2px solid {ACCENT};padding-bottom:10px;margin-bottom:16px;">'
        '<h1 style="font-size:22px;margin:0;">Sample reports</h1>'
        f'<div style="font-size:13px;color:{MUTED};">saas-e2e-reference-architecture</div></div>'
        '<p style="font-size:15px;max-width:720px;">Two real runs of the example suite '
        'against the Demo ESP App, a fictional email service provider. Each report shows '
        'every test and every check, with a video of every browser test; the red run also '
        'keeps the evidence of each failed check.</p>'
        f'<div style="display:flex;flex-wrap:wrap;gap:16px;">{cards}</div>'
        f'<p style="font-size:12px;color:{MUTED};margin-top:20px;">{SOURCE_NOTE}{source}</p>'
        '</main></body></html>')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--green", type=Path, required=True)
    parser.add_argument("--red", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        sys.exit(f"{args.out} is not empty; build into a new folder")
    summaries = {}
    for folder, root in (("green", args.green), ("red", args.red)):
        run = newest_run(root)
        shutil.copytree(long_path(run), long_path(args.out / folder))
        summaries[folder] = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    (args.out / "index.html").write_text(
        landing(summaries["green"], summaries["red"], args.red.name), encoding="utf-8")
    print(f"site built in {args.out}: green {summaries['green']['verdict']}, "
          f"red {summaries['red']['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
