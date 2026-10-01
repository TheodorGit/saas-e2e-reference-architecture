import pytest


@pytest.fixture
def baseline(e2e_ledger):
    """The baseline readings; verification without them has nothing to compare."""
    missing = [k for k in ("journal_max_id", "balance", "dashboard")
               if k not in e2e_ledger.snapshots]
    if missing:
        raise RuntimeError(f"no baseline reading for {missing}: run the baseline stage first")
    return e2e_ledger.snapshots
