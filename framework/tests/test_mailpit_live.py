"""The Mailpit adapter against a real Mailpit.

Needs a running Mailpit (the example's docker compose starts one). Skips, with
the reason stated, when none is reachable - it never passes without one.

    E2E_MAILPIT_URL   default http://localhost:8025
    E2E_SMTP_HOST     default localhost
    E2E_SMTP_PORT     default 1025
"""
import os
import smtplib
import uuid
from email.message import EmailMessage

import pytest
import requests

from framework.delivery.content_checks import one_click_url
from framework.delivery.mailpit import MailpitClient

pytestmark = pytest.mark.integration

URL = os.getenv("E2E_MAILPIT_URL", "http://localhost:8025")
SMTP_HOST = os.getenv("E2E_SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("E2E_SMTP_PORT", "1025"))


@pytest.fixture(scope="module")
def inbox():
    try:
        requests.get(f"{URL}/api/v1/messages", timeout=3).raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"no Mailpit reachable at {URL}: {type(exc).__name__}")
    return MailpitClient(URL)


def send(subject: str, to: list[str], html: str, headers: dict = None):
    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    for name, value in (headers or {}).items():
        message[name] = value
    message.set_content("plain part")
    message.add_alternative(html, subtype="html")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.send_message(message)


def test_the_adapter_reads_back_what_was_sent(inbox):
    token = f"QA-live-{uuid.uuid4().hex[:8]}"
    to = ["qa+a@example.com", "qa+b@example.com"]
    send(f"{token} hello", to, "<p>Hi <a href='https://t.example.com/c/1'>link</a></p>",
         headers={"List-Unsubscribe": "<https://app.example.com/u/1>, <mailto:u@example.com>",
                  "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})
    try:
        found = inbox.wait_for(subject=token, timeout_s=20, poll_s=1)
        assert found is not None, f"no message carrying {token} within 20s"
        assert set(found.to) == set(to)
        assert "https://t.example.com/c/1" in inbox.html(found.id)
        raw = inbox.raw(found.id)
        assert f"Subject: {token} hello".encode() in raw and b"List-Unsubscribe:" in raw
        assert one_click_url(inbox.headers(found.id)) == "https://app.example.com/u/1"
        assert set(inbox.wait_for_each(token, to, timeout_s=5, poll_s=1)) == set(to)
        assert inbox.search(subject=token, to="qa+a@example.com")
        assert not inbox.search(subject=token, to="nobody@example.com")
    finally:
        removed = inbox.delete_matching(subject=token)
    assert removed == 1
    assert inbox.search(subject=token) == []
