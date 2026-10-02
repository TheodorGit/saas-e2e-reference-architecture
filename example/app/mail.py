"""Rendering one recipient's copy of an email, and sending it over SMTP."""
import html
import re
import smtplib
from email import policy
from email.message import EmailMessage
from email.utils import make_msgid

from example.app import bugs
from example.app.settings import SETTINGS

SMTP_POLICY = policy.SMTP.clone(max_line_length=998)

TEMPLATE_VARIABLE = re.compile(r"\{\{\s*(first_name|last_name|email)\s*\}\}")
HREF = re.compile(r"""(<a\b[^>]*?\bhref=)(["'])(.*?)\2""", re.IGNORECASE | re.DOTALL)
HEADER_LINE = "No longer want these emails?"
FOOTER_LINE = "You receive this because you subscribed to Demo ESP App."


def render_variables(text: str, contact: dict, escape: bool) -> str:
    def value(match):
        if match.group(1) == "first_name" and bugs.active("literal_template_variable"):
            return match.group(0)
        found = contact.get(match.group(1)) or ""
        return html.escape(found) if escape else found
    return TEMPLATE_VARIABLE.sub(value, text)


def links_in(body_html: str) -> list[str]:
    seen = []
    for _, _, url in HREF.findall(body_html):
        if not url.lower().startswith("mailto:") and url not in seen:
            seen.append(url)
    return seen


def unsubscribe_url(token: str) -> str:
    return f"{SETTINGS.public_url}/u/{token}"


def track_links(body_html: str, token: str, links: list[str]) -> str:
    def rewrite(match):
        url = match.group(3)
        if url not in links:
            return match.group(0)
        tracked = f"{SETTINGS.public_url}/t/c/{token}/{links.index(url)}"
        return f"{match.group(1)}{match.group(2)}{tracked}{match.group(2)}"
    return HREF.sub(rewrite, body_html)


def render(email: dict, contact: dict, token: str, links: list[str]) -> dict:
    unsubscribe = unsubscribe_url(token)
    body = track_links(render_variables(email["body_html"], contact, escape=True), token, links)
    html_body = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#1f2937;">'
        f'<p style="font-size:12px;color:#6b7280;">{HEADER_LINE} '
        f'<a href="{unsubscribe}">Unsubscribe</a></p>'
        f"<div>{body}</div>"
        '<hr style="border:none;border-top:1px solid #e5e7eb;">'
        f'<p style="font-size:12px;color:#6b7280;">{FOOTER_LINE} '
        f'<a href="{unsubscribe}">Unsubscribe</a> or '
        f'<a href="{unsubscribe}">manage your subscription</a>.</p>'
        f'<img src="{SETTINGS.public_url}/t/o/{token}.gif" width="1" height="1" alt="">'
        "</body></html>")
    text = re.sub(r"<[^>]+>", " ", render_variables(email["body_html"], contact, escape=False))
    text = html.unescape(re.sub(r"[ \t]+", " ", text)).strip()
    text += f"\n\nUnsubscribe: {unsubscribe}\n"
    return {"subject": render_variables(email["subject"], contact, escape=False),
            "html": html_body, "text": text,
            "one_click": f"{SETTINGS.public_url}/u/{token}/one-click",
            "mailto": f"mailto:unsubscribe@demo-esp.test?subject=unsubscribe-{token}"}


def build(rendered: dict, to: str, token: str) -> EmailMessage:
    # 998 is RFC 5322's hard line limit; the default 78 encodes long URIs in headers.
    message = EmailMessage(policy=SMTP_POLICY)
    message["From"] = SETTINGS.sender
    message["To"] = to
    message["Subject"] = rendered["subject"]
    message["Message-ID"] = make_msgid(idstring=token[:16], domain="demo-esp.test")
    message["List-Unsubscribe"] = f"<{rendered['one_click']}>, <{rendered['mailto']}>"
    if not bugs.active("missing_one_click_post"):
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(rendered["text"])
    message.add_alternative(rendered["html"], subtype="html")
    return message


def send_all(messages: list[EmailMessage]):
    with smtplib.SMTP(SETTINGS.smtp_host, SETTINGS.smtp_port, timeout=30) as smtp:
        for message in messages:
            smtp.send_message(message)
