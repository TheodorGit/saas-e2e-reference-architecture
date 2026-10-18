"""The dashboard moved by exactly what the run did, measured from its baseline."""
import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.pages.dashboard import DashboardPage
from framework.polling import poll_until_stable

pytestmark = pytest.mark.pipeline


def test_dashboard_deltas(app_page, e2e_ledger, baseline, config, checks):
    entries = e2e_ledger.entries
    expected = {
        "credits": -kinds.spend(entries)["total"],
        "contacts": kinds.delta(entries, "contacts_delta"),
        "subscribed": kinds.delta(entries, "subscribed_delta"),
        "batches_sent": sum(1 for e in entries if e["kind"] in kinds.SENDS),
    }
    before = baseline["dashboard"]
    dashboard = DashboardPage(app_page)
    dashboard.open()

    def read():
        dashboard.refresh()
        return dashboard.values()
    # Waiting for the figure the run expects stops on it while billing is still landing.
    now, waited = poll_until_stable(read, config.ingest_budget_s, config.ingest_settle_s)

    for key, want in expected.items():
        checks.soft_check(f"{key} delta",
                          lambda key=key, want=want: _delta(before, now, key, want, waited,
                                                            checks),
                          expected=f"moved by {want:+d}, what the run did", ui=True)
    checks.raise_soft_failures()


def _delta(before: dict, now: dict, key: str, want: int, waited: float, checks) -> int:
    moved = now[key] - before[key]
    evidence.data(checks, "the dashboard readings", {"before the run": before,
                                                     "now": now, "the run accounts for": want})
    assert moved == want, f"{key} moved by {moved:+d} ({before[key]} -> {now[key]}), " \
                          f"the run accounts for {want:+d} ({waited:.0f}s allowed)"
    return moved
