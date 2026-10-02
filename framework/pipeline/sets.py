"""Set-difference and partition assertions."""
from collections.abc import Iterable, Mapping

SHOWN = 10


def _norm(items: Iterable) -> set:
    return {i.lower() if isinstance(i, str) else i for i in items or ()}


def _show(items) -> str:
    items = sorted(items, key=str)
    more = f" (+{len(items) - SHOWN} more)" if len(items) > SHOWN else ""
    return f"{items[:SHOWN]}{more}"


def difference(expected: Iterable, observed: Iterable) -> tuple[list, list]:
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
