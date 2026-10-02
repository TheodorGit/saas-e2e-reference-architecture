"""Rolling windows: whether an action falls inside, outside, or too close to call."""
from datetime import datetime, timedelta

DEFAULT_MARGIN_S = 2.0


def position(opened_at: datetime | None, at: datetime, window_s: float,
             margin_s: float = DEFAULT_MARGIN_S) -> bool | None:
    """True inside the window, False outside, None too close to the edge to call."""
    if opened_at is None:
        return False
    elapsed = (at - opened_at).total_seconds()
    if elapsed < 0:
        return None
    if elapsed < window_s - margin_s:
        return True
    if elapsed > window_s + margin_s:
        return False
    return None


def closes_at(opened_at: datetime, window_s: float,
              margin_s: float = DEFAULT_MARGIN_S) -> datetime:
    return opened_at + timedelta(seconds=window_s + margin_s + 0.5)
