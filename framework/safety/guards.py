"""Guards that run BEFORE anything is sent or changed.

A suite that acts on a live system needs rails a normal test does not: it must
refuse to send to an audience larger than it expects, refuse to act on anyone it
does not own, and refuse to touch controlled resources unless explicitly asked.
These are safety stops, not product checks, and they say so when they fire.
"""
import os
from collections.abc import Callable, Iterable

DESTRUCTIVE_ENV = "E2E_ALLOW_DESTRUCTIVE"


def same_inbox(address: str, inbox: str) -> bool:
    """True when `address` is `inbox` or one of its plus-aliases
    (name+anything@domain delivers to name@domain)."""
    def split(value):
        local, _, domain = (value or "").strip().lower().partition("@")
        return local.split("+")[0], domain
    return bool(inbox) and split(address) == split(inbox)


def assert_within_cap(count: int, cap: int, what: str = "audience") -> int:
    assert count <= cap, (
        f"SAFETY STOP: the {what} holds {count}, above the cap of {cap}. "
        f"Refusing to act; check the configuration points at the test {what}.")
    return count


def assert_owned(members: Iterable[str], is_ours: Callable[[str], bool],
                 declared_foreign: Iterable[str] = ()) -> list[str]:
    """Every member is ours or declared up front. Returns the declared foreign
    members actually present, so expectations can allow for them BY NAME."""
    foreign = {f.strip().lower() for f in declared_foreign if f.strip()}
    members = [m.strip().lower() for m in members]
    strangers = [m for m in members if not is_ours(m) and m not in foreign]
    assert not strangers, (
        f"SAFETY STOP: {len(strangers)} member(s) are neither ours nor declared: "
        f"{strangers[:5]}")
    return sorted(m for m in members if m in foreign)


def destructive_allowed() -> bool:
    return os.getenv(DESTRUCTIVE_ENV, "").lower() in ("1", "true", "yes")
