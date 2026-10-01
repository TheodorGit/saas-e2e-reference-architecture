"""Derived totals: ONE function per number, read by every consumer.

The number a report shows and the number a check asserts must come from the same
code, or they drift apart and a reader sees one value while the suite asserts
another. Suites define how each entry kind counts; this module only adds up.
"""
from collections.abc import Callable, Mapping

Counter = Callable[[dict], int]


def tally(entries: list[dict], counters: Mapping[str, Counter]) -> dict:
    """{bucket: total, ..., 'total': sum} where each counter reads one entry.

    A counter returns 0 for entries it does not own, so one entry can feed
    several buckets (units to recipients vs units to a fixed notify address).
    """
    totals = {name: sum(count(e) for e in entries) for name, count in counters.items()}
    totals["total"] = sum(totals.values())
    return totals


def shortfall(entries: list[dict], expected: Counter, observed_field: str) -> int:
    """How far an observed surface falls SHORT of what the run did, summed.

    Measured per entry from what verification actually read (`observed_field`),
    never assumed: an allowance for a known undercount must shrink to zero the
    day the undercount is fixed, with no change to the checks that grant it.
    Entries with no observation are ignored; an overcount contributes nothing
    (an overcount is never an allowance).
    """
    short = 0
    for entry in entries:
        observed = entry.get(observed_field)
        if observed is None:
            continue
        short += max(0, expected(entry) - observed)
    return short
