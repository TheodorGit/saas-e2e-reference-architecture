"""The session ledger: what the run did, recorded the moment it did it.

Action tests do not check their own cost or stats. They RECORD what they spent
and sent, right after the action succeeds, and a verification stage reconciles
the whole run once, after the system has had time to settle. That turns many
racy per-test checks into one exact reconciliation.

Entries are free-form dicts with a few fixed keys; what an entry `kind` means
belongs to the suite using the ledger, never to this module.

The ledger is saved after every write, so a crashed run still leaves a complete
record of what it spent and what it created.

All timestamps are UTC ISO-8601. Mixing local time into a ledger whose entries
are later matched against a system that reports in UTC is a classic source of
checks that silently match nothing.
"""
import json
from datetime import UTC, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, path: Path, replay_of: str = ""):
        self.path = Path(path)
        # Set when the entries belong to an earlier run being replayed.
        self.replay_of = replay_of
        self.entries: list[dict] = []
        # What the run created, for end-of-session cleanup.
        self.entities: list[dict] = []
        # Readings taken once, before the run touched anything.
        self.snapshots: dict = {}

    # --- entries -------------------------------------------------------------

    def record(self, action: str, kind: str, cost: int = 0, planned: int = None,
               name: str = None, token: str = None, **extra) -> dict:
        """Record one action immediately after it succeeded. `cost` is what the
        run expects to be charged; `planned` how many units it aimed at."""
        entry = {"action": action, "kind": kind, "cost": cost, "planned": planned,
                 "name": name, "token": token, "at": utc_now(), **extra}
        self.entries.append(entry)
        self.save()
        return entry

    def update(self, name: str, **fields) -> dict:
        """Add or overwrite fields on the entry recorded under `name`."""
        for entry in self.entries:
            if entry.get("name") == name:
                entry.update(fields)
                self.save()
                return entry
        raise KeyError(f"no ledger entry named {name!r}")

    def find(self, **match) -> list[dict]:
        """Entries whose fields equal every given value."""
        return [e for e in self.entries
                if all(e.get(k) == v for k, v in match.items())]

    def total_cost(self, kinds=None) -> int:
        return sum(e.get("cost") or 0 for e in self.entries
                   if kinds is None or e.get("kind") in kinds)

    # --- entities ------------------------------------------------------------

    def register_entity(self, kind: str, uid: str, name: str,
                        preserve: bool = False) -> dict:
        """Track something the run created. preserve=True keeps it through
        cleanup (a failed test's entity is its evidence). Re-registering the
        same id only updates the flag."""
        for entity in self.entities:
            if entity["id"] == uid:
                entity["preserve"] = preserve
                self.save()
                return entity
        entity = {"kind": kind, "id": uid, "name": name, "preserve": preserve}
        self.entities.append(entity)
        self.save()
        return entity

    def mark_removed(self, uid: str):
        """Flag an entity a test already removed, so cleanup skips it."""
        for entity in self.entities:
            if entity["id"] == uid:
                entity["removed"] = True
        self.save()

    def preserve_all(self):
        """Freeze every entity that exists NOW: called when a test fails. A
        failing check can only have read entities created before it, so those
        are its evidence; anything created afterwards is not, and is cleaned up."""
        for entity in self.entities:
            entity["preserve"] = True
        self.save()

    def cleanup_targets(self) -> list[dict]:
        return [e for e in self.entities
                if not e.get("preserve") and not e.get("removed")]

    # --- snapshots -----------------------------------------------------------

    def snapshot(self, key: str, value):
        """Store a baseline ONCE. A second call keeps the first reading: the
        baseline must be what the system said before the run acted."""
        if key not in self.snapshots:
            self.snapshots[key] = value
            self.save()
        return self.snapshots[key]

    # --- persistence ---------------------------------------------------------

    def to_dict(self) -> dict:
        return {"replay_of": self.replay_of, "entries": self.entries,
                "entities": self.entities, "snapshots": self.snapshots}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.to_dict(), indent=2, default=str),
                             encoding="utf-8")

    @classmethod
    def replay(cls, source: Path, path: Path) -> "Ledger":
        """A ledger carrying an earlier run's entries and snapshots, for
        re-running verification without acting again. Entities are NOT
        carried: cleanup must never touch another run's work."""
        prior = json.loads(Path(source).read_text(encoding="utf-8"))
        if not prior.get("entries"):
            raise ValueError(f"{source} records no entries to replay")
        ledger = cls(path, replay_of=str(source))
        ledger.entries = prior["entries"]
        ledger.snapshots = prior.get("snapshots", {})
        ledger.save()
        return ledger
