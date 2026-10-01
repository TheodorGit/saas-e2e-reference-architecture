"""The dashboard moved by exactly what the run did, measured from its baseline."""
import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.pages.dashboard import DashboardPage
from framework.polling import poll_until

pytestmark = pytest.mark.pipeline


def test_dashboard_deltas(app_page, e2e_ledger, baseline, config, steps):
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
    # Billing lands asynchronously: poll until the balance settles on what the run spent.
    now, waited = poll_until(read, lambda v: v["credits"] - before["credits"] ==
                             expected["credits"], config.ingest_budget_s, 3)

    for key, want in expected.items():
        steps.soft_step(f"{key} delta",
                        lambda key=key, want=want: _delta(before, now, key, want, waited,
                                                          steps),
                        expected=f"moved by {want:+d}, what the run did", ui=True)
    steps.raise_soft_failures()


def _delta(before: dict, now: dict, key: str, want: int, waited: float, steps) -> int:
    moved = now[key] - before[key]
    evidence.data(steps, "the dashboard readings", {"before the run": before,
                                                    "now": now, "the run accounts for": want})
    assert moved == want, f"{key} moved by {moved:+d} ({before[key]} -> {now[key]}), " \
                          f"the run accounts for {want:+d} ({waited:.0f}s allowed)"
    return moved
