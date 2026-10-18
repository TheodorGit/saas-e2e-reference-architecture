"""Screenshots of a run's report email and report, at the width the README uses."""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from framework import tokens

WIDTH = 1100
MAILPIT = os.getenv("E2E_MAILPIT_URL", "http://mailpit:8025").rstrip("/")
SENDER = os.getenv("E2E_REPORT_FROM", "qa-reports@example.com")


def email_id_for(run_id: str) -> str:
    # The inbox holds a report per run, so the run id picks this run's own.
    query = urllib.parse.urlencode({"query": f'from:"{SENDER}" "{run_id}"', "limit": 1})
    with urllib.request.urlopen(f"{MAILPIT}/api/v1/search?{query}", timeout=20) as answer:
        messages = json.load(answer).get("messages") or []
    if not messages:
        raise SystemExit(f"no report email from {SENDER} for run {run_id}")
    return messages[0]["ID"]


GROW_FRAME = """() => {
  const frame = document.querySelector('iframe');
  if (!frame) return 0;
  if (frame.contentDocument) {
    frame.style.height = frame.contentDocument.body.scrollHeight + 'px';
  }
  for (let el = frame.parentElement; el; el = el.parentElement) {
    el.style.overflow = 'visible';
    el.style.height = 'auto';
    el.style.maxHeight = 'none';
  }
  return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
}"""
MAX_HEIGHT = 6000
REPORT_MAX_HEIGHT = 1750


def fit_to_content(page):
    # Mailpit scrolls an inner panel, so a full-page shot would stop at the viewport.
    height = page.evaluate(GROW_FRAME)
    page.set_viewport_size({"width": WIDTH, "height": min(int(height) + 40, MAX_HEIGHT)})


COVER = (1000, 750)
LIFT_THE_FAILURE = """(marker) => {
  document.querySelectorAll('h2').forEach((h) => { h.style.display = 'none'; });
  document.querySelectorAll('details').forEach((card) => {
    if (card.textContent.includes(marker)) { card.open = true; }
    else { card.style.display = 'none'; }
  });
}"""


def shoot_cover(page, target: Path, marker: str):
    # The cover is the verdict with the failure right under it, the rest folded away.
    page.set_viewport_size({"width": COVER[0], "height": COVER[1]})
    page.evaluate(LIFT_THE_FAILURE, marker)
    target.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(target), clip={"x": 0, "y": 0,
                                            "width": COVER[0], "height": COVER[1]})
    print(f"[shot] {target}")


def shoot(page, target: Path, max_height: int = 0):
    target.parent.mkdir(parents=True, exist_ok=True)
    tall = page.evaluate("() => document.documentElement.scrollHeight")
    clip = None
    if max_height and tall > max_height:
        # A failing report runs long; the README shows its head and links the rest.
        clip = {"x": 0, "y": 0, "width": WIDTH, "height": max_height}
    page.screenshot(path=str(target), full_page=True, clip=clip)
    print(f"[shot] {target}")


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "clean"
    run_dir = tokens.newest_run(Path(os.getenv("E2E_RESULTS_DIR", "reports")), label)
    if run_dir is None:
        raise SystemExit(f"no finished run labelled {label}")
    out = run_dir.parent / "images" / label
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_context(viewport={"width": WIDTH, "height": 900}).new_page()

        run_id = run_dir.name.rsplit("-", 1)[0]
        page.goto(f"{MAILPIT}/view/{email_id_for(run_id)}")
        # Mailpit renders the email in a frame; its own chrome is part of the picture.
        expect(page.locator("iframe").first).to_be_visible()
        fit_to_content(page)
        shoot(page, out / "email.png")

        page.set_viewport_size({"width": WIDTH, "height": 900})
        page.goto((run_dir / "report.html").resolve().as_uri())
        expect(page.get_by_text("recorded checks passed").first).to_be_visible()
        shoot(page, out / "report.png", max_height=REPORT_MAX_HEIGHT)
        if label != "clean":
            shoot_cover(page, out / "cover.png", os.getenv("E2E_COVER_TEST", "#8 "))
        browser.close()


if __name__ == "__main__":
    main()
