"""Stage ordering: baseline, then actions, then verification."""
from collections.abc import Iterable, Sequence

DEFAULT_RANK = 1


def parse_stages(lines: Iterable[str]) -> list[tuple[str, int]]:
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
    normalised = str(path).replace("\\", "/")
    for fragment, rank in stages:
        if fragment in normalised:
            return rank
    return default


def order_items(items: list, stages: Sequence[tuple[str, int]]) -> None:
    # pytest regroups parametrized tests, so directory order alone does not hold.
    if not stages:
        return
    items.sort(key=lambda item: stage_of(getattr(item, "path", ""), stages))
