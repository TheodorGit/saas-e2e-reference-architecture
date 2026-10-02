"""Safety guards that run before anything is sent or changed."""
import os
from collections.abc import Callable, Iterable

DESTRUCTIVE_ENV = "E2E_ALLOW_DESTRUCTIVE"


def same_inbox(address: str, inbox: str) -> bool:
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
    foreign = {f.strip().lower() for f in declared_foreign if f.strip()}
    members = [m.strip().lower() for m in members]
    strangers = [m for m in members if not is_ours(m) and m not in foreign]
    assert not strangers, (
        f"SAFETY STOP: {len(strangers)} member(s) are neither ours nor declared: "
        f"{strangers[:5]}")
    return sorted(m for m in members if m in foreign)


def destructive_allowed() -> bool:
    return os.getenv(DESTRUCTIVE_ENV, "").lower() in ("1", "true", "yes")
