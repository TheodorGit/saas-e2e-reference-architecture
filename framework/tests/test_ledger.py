import json

import pytest

from framework.pipeline.ledger import Ledger

pytestmark = pytest.mark.unit


def test_every_write_is_persisted_with_utc_time(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.record("send", "delivery", cost=3, planned=3, name="n1", token="tok")
    on_disk = json.loads((tmp_path / "ledger.json").read_text())
    assert on_disk["entries"][0]["cost"] == 3
    assert on_disk["entries"][0]["at"].endswith("+00:00")


def test_update_find_and_totals(tmp_path):
    ledger = Ledger(tmp_path / "l.json")
    ledger.record("send", "delivery", cost=3, name="a")
    ledger.record("clean", "validation", cost=5, name="b")
    ledger.update("a", opened=["x@example.com"])
    assert ledger.find(kind="delivery")[0]["opened"] == ["x@example.com"]
    assert ledger.total_cost() == 8
    assert ledger.total_cost(kinds={"validation"}) == 5
    with pytest.raises(KeyError):
        ledger.update("missing", x=1)


def test_a_baseline_is_taken_once(tmp_path):
    ledger = Ledger(tmp_path / "l.json")
    ledger.snapshot("dashboard", {"sent": 10})
    assert ledger.snapshot("dashboard", {"sent": 99}) == {"sent": 10}


def test_preserved_or_removed_entities_are_not_cleanup_targets(tmp_path):
    ledger = Ledger(tmp_path / "l.json")
    ledger.register_entity("draft", "1", "a")
    ledger.register_entity("draft", "2", "b", preserve=True)
    ledger.register_entity("draft", "3", "c")
    ledger.mark_removed("3")
    assert [e["id"] for e in ledger.cleanup_targets()] == ["1"]
    ledger.preserve_all()
    assert ledger.cleanup_targets() == []


def test_an_entity_created_after_a_failure_is_not_evidence_and_is_cleaned(tmp_path):
    ledger = Ledger(tmp_path / "l.json")
    ledger.register_entity("draft", "before", "read by the failing check")
    ledger.preserve_all()
    ledger.register_entity("draft", "after", "created later, unrelated")
    assert [e["id"] for e in ledger.cleanup_targets()] == ["after"]


def test_replay_carries_entries_but_never_entities(tmp_path):
    first = Ledger(tmp_path / "first.json")
    first.record("send", "delivery", cost=3, name="a")
    first.register_entity("draft", "1", "a")
    first.snapshot("dashboard", {"sent": 1})
    replayed = Ledger.replay(tmp_path / "first.json", tmp_path / "second.json")
    assert replayed.entries[0]["name"] == "a"
    assert replayed.snapshots == {"dashboard": {"sent": 1}}
    assert replayed.entities == []
    assert replayed.replay_of.endswith("first.json")


def test_replay_refuses_an_empty_ledger(tmp_path):
    Ledger(tmp_path / "empty.json").save()
    with pytest.raises(ValueError):
        Ledger.replay(tmp_path / "empty.json", tmp_path / "out.json")
