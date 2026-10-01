import pytest

from framework.pipeline.totals import shortfall, tally
from framework.polling import poll_until

pytestmark = pytest.mark.unit

ENTRIES = [
    {"kind": "delivery", "planned": 5, "skipped": 1, "observed": 3},
    {"kind": "delivery", "planned": 2, "skipped": 0, "observed": 2},
    {"kind": "notify", "planned": 1},
]


def sent(entry):
    return entry["planned"] - entry.get("skipped", 0) if entry["kind"] == "delivery" else 0


def notified(entry):
    return entry["planned"] if entry["kind"] == "notify" else 0


def test_tally_sums_each_bucket_and_the_total():
    totals = tally(ENTRIES, {"to_recipients": sent, "notifications": notified})
    assert totals == {"to_recipients": 6, "notifications": 1, "total": 7}


def test_shortfall_is_measured_and_an_overcount_is_never_an_allowance():
    assert shortfall(ENTRIES, sent, "observed") == 1
    over = [{"kind": "delivery", "planned": 1, "observed": 5}]
    assert shortfall(over, sent, "observed") == 0


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_polling_returns_on_the_first_read_that_holds():
    clock, reads = FakeClock(), iter([1, 2, 3])
    value, waited = poll_until(lambda: next(reads), lambda v: v == 2, 60, 5,
                               clock=clock, sleep=clock.sleep)
    assert value == 2 and waited == 5


def test_polling_gives_up_at_the_budget_with_the_last_value():
    clock = FakeClock()
    value, waited = poll_until(lambda: "not yet", lambda v: False, 12, 5,
                               clock=clock, sleep=clock.sleep)
    assert value == "not yet" and waited == 12
