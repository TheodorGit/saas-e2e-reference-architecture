"""Set-difference and partition assertions.

A count that matches can hide two errors that cancel out: one expected member
missing and one stranger present. Comparing the SETS names both, so a failure
says who, not just how many.

A partition goes one step further: every member of a universe (say, everyone
the run aimed at) lands in exactly one outcome (received, excluded, unsubscribed),
and no outcome holds anyone from outside the universe.

A check over an EMPTY expected set proves nothing - "nobody unexpected received
it" is also true when nobody was sent anything. So an empty expected set fails,
unless the caller says empty is the point (allow_empty=True).
"""
from collections.abc import Iterable, Mapping

SHOWN = 10


def _norm(items: Iterable) -> set:
    return {i.lower() if isinstance(i, str) else i for i in items or ()}


def _show(items) -> str:
    items = sorted(items, key=str)
    more = f" (+{len(items) - SHOWN} more)" if len(items) > SHOWN else ""
    return f"{items[:SHOWN]}{more}"


def difference(expected: Iterable, observed: Iterable) -> tuple[list, list]:
    """(missing, unexpected): expected but not observed, observed but not expected.
    Strings compare case-insensitively."""
    want, got = _norm(expected), _norm(observed)
    return sorted(want - got, key=str), sorted(got - want, key=str)


def _not_vacuous(items, what: str, allow_empty: bool):
    assert allow_empty or _norm(items), (
        f"{what}: nothing to check - a check over an empty set proves nothing")


def assert_same(expected: Iterable, observed: Iterable, what: str = "members",
                allow_empty: bool = False) -> str:
    expected = list(expected or ())
    _not_vacuous(expected, what, allow_empty)
    missing, unexpected = difference(expected, observed)
    problems = []
    if missing:
        problems.append(f"missing {_show(missing)}")
    if unexpected:
        problems.append(f"unexpected {_show(unexpected)}")
    assert not problems, f"{what} differ: " + "; ".join(problems)
    return f"{len(_norm(expected))} {what}, exactly the expected set"


def assert_disjoint(left: Iterable, right: Iterable, what: str,
                    allow_empty: bool = False) -> str:
    left = list(left or ())
    _not_vacuous(left, what, allow_empty)
    both = sorted(_norm(left) & _norm(right), key=str)
    assert not both, f"{what}: {_show(both)}"
    return f"no overlap ({what.split(':')[0]})"


def assert_partition(universe: Iterable, parts: Mapping[str, Iterable]) -> str:
    """Every member of `universe` is in exactly one part; no part holds an outsider."""
    members = _norm(universe)
    _not_vacuous(members, "partition", allow_empty=False)
    seen: dict = {}
    problems = []
    for name, part in parts.items():
        part = _norm(part)
        outsiders = part - members
        if outsiders:
            problems.append(f"{name} holds non-members {_show(outsiders)}")
        for member in part & members:
            seen.setdefault(member, []).append(name)
    doubled = {m: p for m, p in seen.items() if len(p) > 1}
    if doubled:
        problems.append("in more than one part: " + ", ".join(
            f"{m} ({'/'.join(p)})" for m, p in sorted(doubled.items(), key=str)[:SHOWN]))
    unplaced = members - set(seen)
    if unplaced:
        problems.append(f"in no part {_show(unplaced)}")
    assert not problems, "partition broken: " + "; ".join(problems)
    sizes = ", ".join(f"{name} {len(_norm(part))}" for name, part in parts.items())
    return f"{len(members)} members partitioned: {sizes}"
