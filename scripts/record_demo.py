"""Builds the demo backdrop and records the email batch flow as a video.

    docker compose run --rm -e E2E_VIDEO_SIZE=1280x720 tests python scripts/record_demo.py
"""
import argparse
import os
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from example.suite import config as suite_config  # noqa: E402
from example.suite.app_client import AppApi  # noqa: E402
from example.suite.pages.email_batches import EmailBatchesPage, WizardPage  # noqa: E402

AUDIENCE_TAG = "newsletter"
OPTED_OUT = "Unsubscribed - all mail"
BOUNCED = "Bounced addresses"
INTERNAL = "Internal addresses"

# One reader sits on the opted-out list, so the recorded send holds someone back.
SUPPRESSION = (
    (BOUNCED, ("hard-bounce@example.net", "mailbox-full@example.net",
               "no-such-user@example.org")),
    (OPTED_OUT, ("optout1@example.net", "optout2@example.net", "reader3@example.net")),
    (INTERNAL, ("team@example.net", "billing@example.net")),
)

# Oldest first, so the list shows the scheduled pair above the sent three.
BACKDROP = (
    ("Welcome series - day 1", "Welcome aboard - here is how to start",
     "Set up your first list in three steps.", (), None),
    ("September product update", "What shipped in September",
     "Faster imports, clearer reports and a new audience picker.", (BOUNCED,), None),
    ("Customer survey invite", "Two minutes to tell us what to build next",
     "Six questions, and the results shape the next quarter.", (BOUNCED, OPTED_OUT), None),
    ("October product update", "What shipped in October",
     "Rolling send windows, per-batch suppression and a rebuilt report.", (BOUNCED,), 2),
    ("Autumn offer - early access", "Early access opens Friday",
     "Your account is on the early access list for the autumn plan.",
     (BOUNCED, INTERNAL), 5),
)

RECORDED_NAME = "November product update"
RECORDED_SUBJECT = "What is coming in November"
RECORDED_LINE = "Early access opens Friday for everyone on the list."


def body(line: str) -> str:
    return f"<p>Hello {{{{first_name}}}},</p><p>{line}</p><p>Thanks for reading.</p>"


def send_at(days: int) -> str:
    when = datetime.now(UTC) + timedelta(days=days)
    return when.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()


class DemoWizard(WizardPage):
    def __init__(self, page, type_delay_ms: int):
        super().__init__(page)
        self.type_delay_ms = type_delay_ms

    def message(self, name: str, subject: str, body_html: str):
        self.page.get_by_label("Email batch name").fill(name)
        self.page.get_by_label("Subject").press_sequentially(
            subject, delay=self.type_delay_ms)
        self.page.get_by_label("Message (HTML)").press_sequentially(
            body_html, delay=self.type_delay_ms)
        self._next(3, "Address suppression")


def seed(api: AppApi) -> dict:
    readers = api.contacts()
    if not readers:
        raise SystemExit("no contacts: the app seeds three on an empty database")
    api.bulk_tag([c["id"] for c in readers], AUDIENCE_TAG)

    lists = {row["name"]: row["id"]
             for row in api.call("GET", "/api/address-suppression-lists")}
    for name, emails in SUPPRESSION:
        if name not in lists:
            lists[name] = api.create_suppression(name, emails)["id"]

    for name, subject, line, suppress, days in BACKDROP:
        if api.batch_named(name):
            continue
        payload = {"name": name, "subject": subject, "body_html": body(line),
                   "audience_tag": AUDIENCE_TAG,
                   "suppression_list_ids": [lists[n] for n in suppress]}
        if days:
            payload["send_at"] = send_at(days)
        api.call("POST", "/api/email-batches", json=payload)

    print(f"backdrop: {len(readers)} contacts tagged {AUDIENCE_TAG}, "
          f"{len(lists)} suppression lists, {len(BACKDROP)} batches")
    return lists


def record(api: AppApi, config, args) -> Path:
    width, _, height = args.video_size.partition("x")
    size = {"width": int(width), "height": int(height)}
    staging = Path(args.out).parent / "staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=not args.headed, slow_mo=args.slowmo)
        context = browser.new_context(base_url=config.base_url, viewport=size,
                                      record_video_dir=str(staging),
                                      record_video_size=size)
        context.add_cookies([{"name": "esp_session", "value": api.session_cookie,
                              "url": config.base_url}])
        page = context.new_page()

        started = time.monotonic()
        listing = EmailBatchesPage(page)
        listing.open()
        listing.new()
        wizard = DemoWizard(page, args.type_delay)
        wizard.audience_tag(AUDIENCE_TAG)
        wizard.message(RECORDED_NAME, RECORDED_SUBJECT, body(RECORDED_LINE))
        wizard.suppress(OPTED_OUT)
        listing = wizard.send_now()
        listing.wait_until_sent(RECORDED_NAME, config.mail_budget_s)
        elapsed = time.monotonic() - started

        source = Path(page.video.path())
        context.close()
        browser.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), out)
    shutil.rmtree(staging, ignore_errors=True)
    print(f"UI drive reached Sent in {elapsed:.2f}s (slowmo {args.slowmo}ms, "
          f"typing {args.type_delay}ms)")
    print(f"video: {out}")
    return out


def main() -> int:
    results = os.getenv("E2E_RESULTS_DIR", "reports")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slowmo", type=int, default=int(os.getenv("E2E_SLOWMO_MS", "500")))
    parser.add_argument("--type-delay", type=int, default=40)
    parser.add_argument("--video-size", default=os.getenv("E2E_VIDEO_SIZE", "1280x720"))
    parser.add_argument("--out", default=f"{results}/demo/demo_email_batch.webm")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()

    config = suite_config.load()
    api = AppApi(config.base_url, config.email, config.password)
    seed(api)
    if args.seed_only:
        return 0
    if api.batch_named(RECORDED_NAME):
        # The row locator matches by name, so a second copy would make it ambiguous.
        raise SystemExit(f"{RECORDED_NAME!r} already exists: recreate the database with "
                         "docker compose down -v before the next take")
    record(api, config, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
