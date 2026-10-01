"""Links in delivered mail, and engagement the run fires itself.

A tracking system counts an open only when its pixel is fetched and a click only
when a tracked link is. Firing those requests from the run turns engagement into
numbers the run OWNS, recorded against the address whose copy was engaged: a
count can then always be traced back to the contacts that produced it, and a
surplus to someone who is not the run.

Tracker URL shapes are product-specific, so they are passed in as patterns.
"""
import re
from dataclasses import dataclass

import requests

from framework.delivery.mail_client import MailClient, Message

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_ANCHOR = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                     re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class TrackerPatterns:
    open_pixel: str   # regex matching the open-tracking image URL
    click: str        # regex matching a click-tracked link


def anchors(html: str) -> list[tuple[str, str]]:
    """Every (href, visible text) in the body."""
    return [(href, _SPACE.sub(" ", _TAG.sub("", text)).strip())
            for href, text in _ANCHOR.findall(html or "")]


def find_open_pixel(html: str, patterns: TrackerPatterns) -> str | None:
    for src in re.findall(r"<img\b[^>]*src=[\"']([^\"']+)[\"']", html or "", re.I):
        if re.search(patterns.open_pixel, src):
            return src
    return None


def find_link(html: str, text: str) -> str | None:
    """The href of the first anchor whose visible text contains `text`."""
    return next((href for href, label in anchors(html) if text in label), None)


def is_tracked(href: str, patterns: TrackerPatterns) -> bool:
    return bool(re.search(patterns.click, href or ""))


def find_unsubscribe_link(html: str, anchor_texts=(), context_phrases=()) -> str | None:
    """The unsubscribe link, found by what the reader sees, not by URL shape:
    tracked links are opaque, so the anchor text is the only reliable signal.
    Tries configured anchor texts, then 'unsubscribe' in the text, then an
    anchor that closes a sentence starting with one of `context_phrases`."""
    wanted = {t.strip().lower() for t in anchor_texts if t.strip()}
    for href, label in anchors(html):
        if href.lower().startswith("mailto:"):
            continue
        if label.lower() in wanted or "unsubscribe" in label.lower():
            return href
    for phrase in context_phrases:
        match = re.search(re.escape(phrase) + r"[^<>]{0,160}<a\b[^>]*href=[\"']([^\"']+)",
                          html or "", re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def fire(url: str, timeout: float = 15) -> dict:
    """GET a tracker the way a mail client would. Never raises: the result
    says what happened, and the caller decides whether that is a failure."""
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": BROWSER_UA})
        return {"url": url, "status": response.status_code,
                "ok": response.status_code < 400, "reason": ""}
    except requests.RequestException as exc:
        return {"url": url, "status": None, "ok": False,
                "reason": f"{type(exc).__name__}: {exc}"}


def engage(inbox: MailClient, copies: dict[str, Message], patterns: TrackerPatterns,
           open_mail: bool = True, click_text: str = None) -> dict:
    """Open and/or click each recipient's own copy, and say WHO was engaged.

    Returns {"opened": [...], "clicked": [...], "failures": [...]}. Counts are
    len() of the address lists, so a count and its addresses cannot disagree.
    A fetch that failed is reported as a failure, never counted as engagement.
    """
    opened, clicked, failures = [], [], []
    for address, message in sorted(copies.items()):
        body = inbox.html(message.id)
        if open_mail:
            pixel = find_open_pixel(body, patterns)
            if not pixel:
                failures.append(f"{address}: open - no open pixel in the body")
            else:
                result = fire(pixel)
                if result["ok"]:
                    opened.append(address)
                else:
                    failures.append(f"{address}: open - {_why(result)}")
        if click_text:
            href = find_link(body, click_text)
            if not href:
                failures.append(f"{address}: click - no link with text {click_text!r}")
            elif not is_tracked(href, patterns):
                failures.append(f"{address}: click - link is not tracked: {href}")
            else:
                result = fire(href)
                if result["ok"]:
                    clicked.append(address)
                else:
                    failures.append(f"{address}: click - {_why(result)}")
    return {"opened": opened, "clicked": clicked, "failures": failures}


def _why(result: dict) -> str:
    return result["reason"] or f"tracker answered {result['status']}"
