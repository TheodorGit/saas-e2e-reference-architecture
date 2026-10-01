"""Docs coverage: a documented endpoint that no test executed this session is red.

API documentation is a promise; an endpoint in it that nothing calls is an
untested promise, and it rots silently. The check compares the documented
endpoints (method + route template, from the product's own index or spec) with
the ones the session's recorders actually called, and names both sides:
documented but never executed, and executed but not documented.

"This session" is literal: a run that selects a subset of tests exercises a
subset of the API, and the check says so instead of trusting an earlier run.
"""
from collections.abc import Iterable

from framework.api.recorder import Coverage
from framework.pipeline.sets import difference


def key(method: str, template: str) -> str:
    return f"{method.upper()} {template}"


def gaps(documented: Iterable[tuple[str, str]], coverage: Coverage) -> tuple[list, list]:
    """(documented but never executed, executed but not documented)."""
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
