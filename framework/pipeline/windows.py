"""Rolling windows: deciding an expectation against a window that moves.

Many rules depend on "within the last N seconds": a repeat inside the window is
free, a rate limit resets, a metric counts only recent rows. A run that hardcodes
the outcome ("the second one is free") is right until the run is slow, and then
it is wrong in a way that looks like a product defect.

So the expectation is DECIDED per action, from the run's own record of when the
window opened and when the action happened. Near the edge, the run's clock and
the system's clock cannot both be trusted to the second, so the answer there is
None: too close to call. The caller then observes what the system did and
records it, and the exact reconciliation later uses the observed value.
"""
from datetime import datetime, timedelta

DEFAULT_MARGIN_S = 2.0


def position(opened_at: datetime | None, at: datetime, window_s: float,
             margin_s: float = DEFAULT_MARGIN_S) -> bool | None:
    """True when `at` is inside the window opened at `opened_at`, False when it
    is outside (or no window is open), None when within `margin_s` of the edge."""
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
    """The first moment `position` answers False for a window opened at `opened_at`."""
    return opened_at + timedelta(seconds=window_s + margin_s + 0.5)
