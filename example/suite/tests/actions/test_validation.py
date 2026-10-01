"""Validating one address: billed, free again inside the free window, billed after it.

The free window is a ROLLING window, so whether a validation is free is decided per
action from the run's own clock, never hardcoded. Too close to the edge to
call, the run observes what was charged and records that instead.
"""
import time
from datetime import UTC, datetime

import pytest

from example.suite import ledger_kinds as kinds
from example.suite.pages.validate import ValidatePage
from framework.pipeline import windows
from framework.pipeline.expectations import OBSERVE, check
from framework.polling import poll_until

pytestmark = pytest.mark.pipeline

VALIDATION_COST = 5  # the product's price for one billed validation
CLOCK_STEP_BUDGET_S = 10  # how far behind the wall clock may fall during the sleep


def test_validate_single_address(app_page, config, entity_name, record, steps):
    page = ValidatePage(app_page)
    page.open()
    token = entity_name("validate")
    email = config.address(token)
    state = {"opened_at": None, "window_s": 0}

    def validate(number: int, label: str):
        expected_free = windows.position(state["opened_at"], datetime.now(UTC),
                                         state["window_s"])
        result = page.validate(email)
        body = result["body"]
        state["window_s"] = body["free_window_s"]
        shown_free = result["charge"].startswith("Free")
        cost = body["cost"] if expected_free is OBSERVE else \
            (0 if expected_free else VALIDATION_COST)
        record("validation", kinds.VALIDATION, cost=cost, name=f"{token}-{number}",
               token=token, email=email, reference=body["reference"],
               expected_free=expected_free)
        check(steps, f"validation {number} ({label}): free", expected_free, shown_free,
              f"validation {number} shown as free",
              means="The free window did not apply the way the product promises.", ui=True)
        if not shown_free:
            steps.step(f"validation {number}: charge shown",
                       lambda: _charged(result["charge"]),
                       expected=f"'Charged {VALIDATION_COST} credits'", ui=True)
            state["opened_at"] = datetime.now(UTC)

    validate(1, "first time")
    validate(2, "again at once")

    closes = windows.closes_at(state["opened_at"], state["window_s"])
    wait_s = (closes - datetime.now(UTC)).total_seconds()
    if wait_s > config.max_window_wait_s:
        steps.skip_step("validation 3 (after the window)",
                        f"the free window is {state['window_s']}s, longer than the "
                        f"{config.max_window_wait_s}s this run may wait",
                        expected="billed again once the window has closed")
        return
    # A rolling window closes by the clock; nothing observable announces it.
    time.sleep(max(0.0, wait_s))
    # The wall clock can step back during a sleep (VM time sync): confirm it passed.
    _, extra = poll_until(lambda: datetime.now(UTC), lambda now: now >= closes,
                          CLOCK_STEP_BUDGET_S, 0.2)
    steps.step("the window has closed by the wall clock",
               lambda: _passed(datetime.now(UTC), closes, extra),
               expected="the clock is past the window's edge plus its margin")
    validate(3, "after the window")


def _passed(now: datetime, closes: datetime, extra: float) -> str:
    assert now >= closes, f"the wall clock is still {(closes - now).total_seconds():.1f}s " \
                          f"short of the window's edge after {extra:.1f}s more"
    return f"{extra:.1f}s beyond the sleep"


def _charged(text: str) -> str:
    assert text == f"Charged {VALIDATION_COST} credits", f"charge shown as {text!r}"
    return text
