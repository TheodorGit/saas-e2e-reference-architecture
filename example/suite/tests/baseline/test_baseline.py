"""Baseline: read every surface verification compares against, before acting."""
import pytest

from example.suite.pages.dashboard import DashboardPage

pytestmark = pytest.mark.pipeline


def _newest(top: int) -> str:
    return (f"Newest row is #{top}; this run's rows will come after it" if top
            else "The journal is empty; every row from here on is this run's")


def _panels(values: dict) -> str:
    return (f"Credits {values['credits']:,} - contacts {values['contacts']:,} - "
            f"subscribed {values['subscribed']:,} - "
            f"email batches sent {values['batches_sent']:,}")


def test_baseline_readings(app_page, public_api, e2e_ledger, checks):
    journal = public_api.credits()["journal"]
    checks.check("Read the billing journal",
                 lambda: e2e_ledger.snapshot("journal_max_id",
                                             max((r["id"] for r in journal), default=0)),
                 expected="the newest journal row, so this run's rows can be told apart",
                 found=_newest)
    checks.check("Read the balance through the public API",
                 lambda: e2e_ledger.snapshot("balance", public_api.credits()["balance"]),
                 expected="the credit balance before the run acts",
                 found=lambda balance: f"{balance:,} credits")

    dashboard = DashboardPage(app_page)
    dashboard.open()
    checks.check("Read the dashboard",
                 lambda: e2e_ledger.snapshot("dashboard", dashboard.values()),
                 expected="every panel painted a number", found=_panels, ui=True)
