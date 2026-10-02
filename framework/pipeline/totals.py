"""Totals derived from ledger entries, shared by the report and the checks."""
from collections.abc import Callable, Mapping

Counter = Callable[[dict], int]


def tally(entries: list[dict], counters: Mapping[str, Counter]) -> dict:
    totals = {name: sum(count(e) for e in entries) for name, count in counters.items()}
    totals["total"] = sum(totals.values())
    return totals


def shortfall(entries: list[dict], expected: Counter, observed_field: str) -> int:
    """How far a surface falls short of the run, summed per entry; an overcount adds nothing."""
    short = 0
    for entry in entries:
        observed = entry.get(observed_field)
        if observed is None:
            continue
        short += max(0, expected(entry) - observed)
    return short
