"""Replay: re-run verification against state an earlier run recorded.

Verification that reads slow, asynchronous surfaces can take an hour to reach.
Replaying a finished run's state exercises every read path in minutes, for zero
actions and zero cost. It is a development aid, never a run mode: it proves the
checks can READ the surfaces, never that a fresh action behaves.

A green replay must never pass for a real run, so it is announced in the pytest
header (a print inside a fixture only surfaces when something fails).
"""
import os


def replay_source(env_var: str) -> str:
    """The prior run's state file named by `env_var`, or ''."""
    return os.getenv(env_var, "").strip()


def header_lines(label: str, source: str) -> list[str]:
    return [f"{label} REPLAY: state read from {source}",
            "  nothing is acted on, no entities are owned, cleanup is off"]
