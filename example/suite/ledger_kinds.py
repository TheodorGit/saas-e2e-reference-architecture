"""What each ledger entry kind means for Demo ESP App, and how it counts.

The framework ledger stores free-form entries; the meaning lives here. Every
number the report shows and every total a check asserts is derived through
COUNTERS, so the two can never disagree.
"""
from framework.pipeline import totals

VALIDATION = "validation"         # one address validation: cost 5, or 0 inside the free window
SEND = "send"                    # an email batch whose report is cross-checked
UNSUBSCRIBE_SEND = "unsub_send"  # an email batch whose recipients unsubscribe
AUTOMATION = "automation"        # an automation's emails: not billed, not in any report
CONTACT = "contact"              # a contact added or deleted
STATUS = "status"                # a subscription status change

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
