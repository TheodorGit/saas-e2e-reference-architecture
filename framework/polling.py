"""Polling for a condition within a time budget."""
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def poll_until(read: Callable[[], T], done: Callable[[T], bool], budget_s: float,
               poll_s: float = 5.0, clock=None, sleep=None) -> tuple[T, float]:
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    started = clock()
    while True:
        value = read()
        waited = clock() - started
        if done(value) or waited >= budget_s:
            return value, waited
        sleep(max(0.0, min(poll_s, budget_s - waited)))  # bounded poll interval
