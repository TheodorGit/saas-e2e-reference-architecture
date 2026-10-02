"""Mails a built run report: the email body inline, the full report attached."""
import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def recipients() -> list[str]:
    return [a.strip() for a in os.getenv("E2E_REPORT_TO", "").split(",") if a.strip()]


def build_message(run_dir: Path, to: list[str], sender: str) -> EmailMessage:
    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    counts = summary["counts"]
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    msg["From"] = sender
    msg["Subject"] = summary["subject"]
    msg.set_content(f"{summary['subject']}\n\n{counts['passed']} passed, "
                    f"{counts['failed']} failed, {counts['skipped']} skipped.\n"
                    "The full report is attached as HTML.")
    msg.add_alternative((run_dir / "email.html").read_text(encoding="utf-8"),
                        subtype="html")
    report = run_dir / "report.html"
    if report.exists():
        msg.add_attachment(report.read_bytes(), maintype="text", subtype="html",
                           filename=f"report_{summary['run_id']}.html")
    return msg


def send_report(run_dir) -> bool:
    to = recipients()
    if not to:
        print("[mail] E2E_REPORT_TO not set - report not mailed")
        return False
    sender = os.getenv("E2E_REPORT_FROM", "qa-reports@example.com")
    host = os.getenv("E2E_SMTP_HOST", "localhost")
    port = int(os.getenv("E2E_SMTP_PORT", "1025"))
    try:
        message = build_message(Path(run_dir), to, sender)
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.send_message(message)
        print(f"[mail] report sent to {', '.join(to)} via {host}:{port}")
        return True
    except Exception as exc:  # a mail problem must not fail the run
        print(f"[mail] could not send report: {exc}")
        return False
