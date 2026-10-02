"""An unsubscribe is not engagement."""
import json

import pytest

from example.suite import ledger_kinds as kinds
from framework.pipeline.expectations import OBSERVE, check
from framework.polling import poll_until

pytestmark = pytest.mark.pipeline


def test_unsubscribe_is_not_engagement(public_api, e2e_ledger, config, steps):
    sends = [e for e in e2e_ledger.entries if e["kind"] == kinds.UNSUBSCRIBE_SEND]
    if not sends:
        pytest.skip("no unsubscribe email batch to verify")

    for entry in sends:
        if not entry["unsubscribed"] or not entry["opened"]:
            # The unsubscribe test stopped early: nothing to check, and that is not a pass.
            steps.skip_step(f"{entry['name']}: unsubscribes", "no unsubscribe and marker were "
                            f"recorded; see {entry.get('test', 'the unsubscribe test')}",
                            expected="an unsubscribe is never counted as a click")
            continue
        marker = set(entry["opened"])
        report, waited = poll_until(lambda entry=entry: public_api.report(entry["batch_id"]),
                                    lambda r, marker=marker: marker <= set(r["opened_by"]),
                                    config.ingest_budget_s, 2)

        def landed(report=report, waited=waited, marker=marker):
            assert marker <= set(report["opened_by"]), (
                f"the marker open {sorted(marker)} is not in the report after {waited:.0f}s")
        steps.step(f"{entry['name']}: marker landed", landed,
                   expected="the open fired after the unsubscribes is counted")

        seen = ("the report the API returned", json.dumps(report, indent=2), "json")
        for address in entry["unsubscribed"]:
            check(steps, f"{address}: unsubscribe as click", False,
                  address in report["clicked_by"], "an unsubscribe counted as a click",
                  means="Unsubscribing inflates click numbers.", evidence=seen)
        for address in entry["one_click"]:
            check(steps, f"{address}: one-click as open", OBSERVE,
                  address in report["opened_by"], "a one-click unsubscribe counted as an open")
