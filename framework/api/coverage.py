"""Docs coverage: documented endpoints against the ones this session executed."""
from collections.abc import Iterable

from framework.api.recorder import Coverage
from framework.pipeline.sets import difference


def key(method: str, template: str) -> str:
    return f"{method.upper()} {template}"


def gaps(documented: Iterable[tuple[str, str]], coverage: Coverage) -> tuple[list, list]:
    return difference([key(m, t) for m, t in documented], coverage.executed())


def assert_exercised(documented: Iterable[tuple[str, str]], coverage: Coverage) -> str:
    documented = list(documented)
    assert documented, "no documented endpoints: coverage of nothing proves nothing"
    missing, undocumented = gaps(documented, coverage)
    problems = []
    if missing:
        problems.append(f"documented but no test executed them this session: {missing}")
    if undocumented:
        problems.append(f"executed but not documented: {undocumented}")
    assert not problems, "; ".join(problems)
    return f"all {len(documented)} documented endpoints executed this session"
