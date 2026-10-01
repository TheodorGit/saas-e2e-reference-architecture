"""Stage ordering: baseline, then actions, then verification.

A staged suite reads the system before it touches it, acts, then reconciles what
the system now says against what the run recorded. Directory order alone does
not hold that: pytest regroups tests that share parametrized fixtures (every
browser test under pytest-playwright), which moves browser-less tests to the end
of the session - after the checks that were meant to reconcile them.

Ordering is therefore imposed explicitly, by path, with a stable sort so the
order inside each stage is untouched.
"""
from collections.abc import Iterable, Sequence

DEFAULT_RANK = 1


def parse_stages(lines: Iterable[str]) -> list[tuple[str, int]]:
    """Parse 'path/fragment/ = rank' lines (the e2e_stages ini option)."""
    stages = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fragment, sep, rank = line.rpartition("=")
        if not sep:
            raise ValueError(f"stage line needs 'fragment = rank': {raw!r}")
        stages.append((fragment.strip().replace("\\", "/"), int(rank)))
    return stages


def stage_of(path: str, stages: Sequence[tuple[str, int]],
             default: int = DEFAULT_RANK) -> int:
    """The rank of the first stage whose fragment appears in `path`."""
    normalised = str(path).replace("\\", "/")
    for fragment, rank in stages:
        if fragment in normalised:
            return rank
    return default


def order_items(items: list, stages: Sequence[tuple[str, int]]) -> None:
    """Sort collected pytest items by stage, in place and stably."""
    if not stages:
        return
    items.sort(key=lambda item: stage_of(getattr(item, "path", ""), stages))
