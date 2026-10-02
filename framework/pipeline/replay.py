"""Replay: run verification against an earlier run's recorded state."""
import os


def replay_source(env_var: str) -> str:
    return os.getenv(env_var, "").strip()


def header_lines(label: str, source: str) -> list[str]:
    return [f"{label} REPLAY: state read from {source}",
            "  nothing is acted on, no entities are owned, cleanup is off"]
