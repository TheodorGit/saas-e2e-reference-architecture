"""The billing journal reconciles exactly with what the run recorded."""
from collections import Counter, defaultdict

import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from framework.pipeline.sets import assert_disjoint, assert_same
from framework.polling import poll_until

pytestmark = pytest.mark.pipeline


def test_billing_journal_reconciles(public_api, e2e_ledger, baseline, config, steps):
    billable = [e for e in e2e_ledger.entries if e["kind"] in kinds.BILLABLE]
    charged = {e["reference"]: e["cost"] for e in billable if e["cost"]}
    free = [e["reference"] for e in billable if not e["cost"]]
    if not billable:
        pytest.skip("no billable action to reconcile")

    journal, waited = poll_until(
        lambda: public_api.journal_since(baseline["journal_max_id"]),
        lambda rs: set(charged) <= {r["reference"] for r in rs}, config.ingest_budget_s, 2)
    read = {"journal rows since the baseline": journal,
            "billed actions the run recorded": charged, "free validations": free}

    def seen(check):
        def run():
            evidence.data(steps, "the journal rows and the run's record", read)
            return check()
        return run
    amounts, counts = defaultdict(int), Counter()
    for row in journal:
        amounts[row["reference"]] += row["credits"]
        counts[row["reference"]] += 1

    steps.soft_step("every billed action has a row, and no row is unexplained",
                    seen(lambda: assert_same(charged, amounts, f"journal references "
                                             f"({waited:.0f}s allowed to land)")),
                    expected=f"exactly the run's {len(charged)} billed actions",
                    means="Billing does not match what the run did.")

    def one_row_each():
        repeated = {ref: n for ref, n in counts.items() if n > 1}
        assert not repeated, f"billed more than once: {repeated}"
    steps.soft_step("one row per billable action", seen(one_row_each),
                    expected="no action appears twice in the journal",
                    means="An action was billed more than once.")

    def exact_amounts():
        wrong = {ref: (cost, amounts.get(ref, 0)) for ref, cost in charged.items()
                 if amounts.get(ref, 0) != cost}
        assert not wrong, f"(expected, charged) differ: {wrong}"
    steps.soft_step("each row charges exactly the recorded cost", seen(exact_amounts),
                    expected="journal credits equal the ledger's cost, per action")
    if free:
        steps.soft_step("free validations were not billed",
                        seen(lambda: assert_disjoint(free, amounts,
                                                     "free validations with a journal row")),
                        expected=f"{len(free)} validation(s) inside the free window have no row")
    else:
        steps.skip_step("free validations were not billed",
                        "this run recorded no validation inside the free window",
                        expected="validations inside the free window have no row")

    def totals():
        expected = kinds.spend(billable)
        got = sum(amounts.values())
        assert got == expected["total"], f"journal total {got}, run spent {expected}"
        return got
    steps.soft_step("the journal total equals the run's spend", seen(totals),
                    expected="one total, from the same tally the report shows")
    steps.raise_soft_failures()
