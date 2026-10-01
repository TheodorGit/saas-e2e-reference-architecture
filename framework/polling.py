"""Confirm, don't wait.

Never sleep a fixed duration for something that can be observed: poll for the
real condition, within a bounded budget, and report how long it took. The budget
is a cap, not a wait - a healthy system returns on the first read that holds.

Spending real time before giving up is also what separates "the surface has not
caught up yet" from "it never happened" on systems that ingest asynchronously.
"""
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def poll_until(read: Callable[[], T], done: Callable[[T], bool], budget_s: float,
               poll_s: float = 5.0, clock=None, sleep=None) -> tuple[T, float]:
    """Call read() until done(value) or the budget is spent.

    Returns (last value, seconds waited) so the caller can state, in its own
    failure message, how long the surface was given.
    """
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    started = clock()
    while True:
        value = read()
        waited = clock() - started
        if done(value) or waited >= budget_s:
            return value, waited
        sleep(max(0.0, min(poll_s, budget_s - waited)))  # bounded poll interval
