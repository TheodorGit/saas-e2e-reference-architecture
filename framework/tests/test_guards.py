import pytest

from framework.safety.guards import assert_owned, assert_within_cap, destructive_allowed, same_inbox

pytestmark = pytest.mark.unit

INBOX = "qa@example.com"


def test_plus_aliases_are_the_same_inbox():
    assert same_inbox("qa+run1@example.com", INBOX)
    assert same_inbox("QA@Example.com", INBOX)
    assert not same_inbox("qa@other.example", INBOX)
    assert not same_inbox("qa2@example.com", INBOX)


def test_cap_is_a_safety_stop():
    assert assert_within_cap(10, 10) == 10
    with pytest.raises(AssertionError, match="SAFETY STOP"):
        assert_within_cap(11, 10)


def test_every_member_is_ours_or_declared():
    members = ["qa+1@example.com", "friend@example.org"]
    present = assert_owned(members, lambda m: same_inbox(m, INBOX),
                           declared_foreign=["friend@example.org"])
    assert present == ["friend@example.org"]
    with pytest.raises(AssertionError, match="neither ours nor declared"):
        assert_owned(members, lambda m: same_inbox(m, INBOX))


def test_destructive_needs_an_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("E2E_ALLOW_DESTRUCTIVE", raising=False)
    assert not destructive_allowed()
    monkeypatch.setenv("E2E_ALLOW_DESTRUCTIVE", "1")
    assert destructive_allowed()
