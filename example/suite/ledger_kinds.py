"""The Demo ESP App's ledger entry kinds, and how each counts."""
from framework.pipeline import totals

VALIDATION = "validation"
SEND = "send"
UNSUBSCRIBE_SEND = "unsub_send"
AUTOMATION = "automation"
CONTACT = "contact"
STATUS = "status"

SENDS = (SEND, UNSUBSCRIBE_SEND)
BILLABLE = (VALIDATION, *SENDS)

COUNTERS = {
    "validation": lambda e: (e.get("cost") or 0) if e["kind"] == VALIDATION else 0,
    "sending": lambda e: (e.get("cost") or 0) if e["kind"] in SENDS else 0,
}


def spend(entries: list[dict]) -> dict:
    return totals.tally(entries, COUNTERS)


def delta(entries: list[dict], field: str) -> int:
    return sum(e.get(field) or 0 for e in entries)
