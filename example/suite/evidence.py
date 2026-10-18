"""Evidence helpers for Demo ESP App checks."""
import json

from framework.delivery.mail_client import MailClient, Message
from framework.reporting.recorder import CheckRecorder


def email(checks: CheckRecorder, inbox: MailClient, message: Message, label: str):
    checks.attach(label, inbox.html(message.id) or "(this email has no HTML part)", "html")
    checks.attach(label, inbox.raw(message.id), "eml")
    headers = "\n".join(f"{k}: {v}" for k, v in inbox.headers(message.id).items())
    checks.attach(f"{label} - headers", headers)


def inbox_listing(checks: CheckRecorder, inbox: MailClient, subject: str, label: str):
    found = inbox.search(subject=subject)
    lines = [f"{len(found)} message(s) with {subject!r} in the subject:"]
    lines += [f"- to {', '.join(m.to)} | {m.subject} | {m.received_at}" for m in found]
    checks.attach(label, "\n".join(lines))


def data(checks: CheckRecorder, label: str, value):
    checks.attach(label, json.dumps(value, indent=2, default=str), "json")
