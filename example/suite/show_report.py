"""End a watched run on its result: the live view shows the report email as it
arrived in the inbox, then the full report it attaches.

    python example/suite/show_report.py

Run by entrypoint.sh after pytest, only when the live view is on. Each page stays on
screen for E2E_SHOW_REPORT_S seconds (0 skips this), scrolled slowly so a viewer
sees all of it. It never changes the run's outcome: a problem here is printed and
the run ends as it would have.
"""
import os
import re
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from framework.polling import poll_until

SCREEN = (1440, 900)  # the live view's virtual screen (entrypoint.sh)
MAIL_BUDGET_S = 15    # the report is mailed before pytest exits; this is a margin


def report_email_id(mailpit: str, sender: str) -> str | None:
    """The newest message from the report sender, or None within the budget."""
    def newest():
        response = requests.get(f"{mailpit}/api/v1/search", timeout=10,
                                params={"query": f'from:"{sender}"', "limit": 1})
        response.raise_for_status()
        return (response.json().get("messages") or [None])[0]
    found, _ = poll_until(newest, bool, MAIL_BUDGET_S, 1)
    return found["ID"] if found else None


def latest_report(latest_page: Path) -> Path | None:
    """The report latest.html points at."""
    match = re.search(r'url=([^"]+)', latest_page.read_text(encoding="utf-8"))
    return (latest_page.parent / match.group(1).replace("%20", " ")) if match else None


def present(page, seconds: float):
    """Hold the page on screen: a third of the time at the top, then a slow scroll."""
    page.mouse.move(SCREEN[0] / 2, SCREEN[1] / 2)
    time.sleep(seconds / 3)  # the viewer reads the top first
    steps = 12
    for _ in range(steps):
        page.mouse.wheel(0, 260)
        time.sleep(seconds * 2 / 3 / steps)  # a pace a person can follow


def main():
    seconds = float(os.getenv("E2E_SHOW_REPORT_S", "30"))
    if seconds <= 0:
        return
    mailpit = os.getenv("E2E_MAILPIT_URL", "http://localhost:8025").rstrip("/")
    sender = os.getenv("E2E_REPORT_FROM", "qa-reports@example.com")
    latest = Path(os.getenv("E2E_LATEST_PAGE", "reports/latest.html"))
    email_id = report_email_id(mailpit, sender) if os.getenv("E2E_REPORT_TO") else None
    report = latest_report(latest) if latest.exists() else None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[f"--window-size={SCREEN[0]},{SCREEN[1]}", "--window-position=0,0"])
        page = browser.new_context(no_viewport=True).new_page()
        if email_id:
            print("[show] the report email, as it arrived in the inbox")
            page.goto(f"{mailpit}/view/{email_id}")
            page.wait_for_load_state("networkidle")
            present(page, seconds)
        if report and report.exists():
            print("[show] the full report it attaches")
            page.goto(report.resolve().as_uri())
            present(page, seconds)
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # showing the result must never change it
        print(f"[show] could not show the report: {type(exc).__name__}: {exc}")
