"""What Demo ESP App checks attach as evidence: kept only if the check fails.

Each helper is called INSIDE a check, before it asserts, so the evidence belongs
to that check and reaches the evidence folder only when the check goes red.
"""
import json

from framework.delivery.mail_client import MailClient, Message
from framework.reporting.recorder import StepRecorder


def email(steps: StepRecorder, inbox: MailClient, message: Message, label: str):
    """The delivered email: open the .html in a browser, the .eml in a mail client."""
    steps.attach(label, inbox.html(message.id) or "(this email has no HTML part)", "html")
    steps.attach(label, inbox.raw(message.id), "eml")
    headers = "\n".join(f"{k}: {v}" for k, v in inbox.headers(message.id).items())
    steps.attach(f"{label} - headers", headers)


def inbox_listing(steps: StepRecorder, inbox: MailClient, subject: str, label: str):
    """Everything the inbox holds for this send, and who each copy went to."""
    found = inbox.search(subject=subject)
    lines = [f"{len(found)} message(s) with {subject!r} in the subject:"]
    lines += [f"- to {', '.join(m.to)} | {m.subject} | {m.received_at}" for m in found]
    steps.attach(label, "\n".join(lines))


def data(steps: StepRecorder, label: str, value):
    """Rows, a report, a response body: what a reconciliation read."""
    steps.attach(label, json.dumps(value, indent=2, default=str), "json")
