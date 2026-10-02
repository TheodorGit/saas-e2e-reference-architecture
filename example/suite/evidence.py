"""Evidence helpers for Demo ESP App checks."""
import json

from framework.delivery.mail_client import MailClient, Message
from framework.reporting.recorder import StepRecorder


def email(steps: StepRecorder, inbox: MailClient, message: Message, label: str):
    steps.attach(label, inbox.html(message.id) or "(this email has no HTML part)", "html")
    steps.attach(label, inbox.raw(message.id), "eml")
    headers = "\n".join(f"{k}: {v}" for k, v in inbox.headers(message.id).items())
    steps.attach(f"{label} - headers", headers)


def inbox_listing(steps: StepRecorder, inbox: MailClient, subject: str, label: str):
    found = inbox.search(subject=subject)
    lines = [f"{len(found)} message(s) with {subject!r} in the subject:"]
    lines += [f"- to {', '.join(m.to)} | {m.subject} | {m.received_at}" for m in found]
    steps.attach(label, "\n".join(lines))


def data(steps: StepRecorder, label: str, value):
    steps.attach(label, json.dumps(value, indent=2, default=str), "json")
