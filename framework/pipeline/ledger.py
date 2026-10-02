"""The session ledger: what the run did, spent and created."""
import json
from datetime import UTC, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, path: Path, replay_of: str = ""):
        self.path = Path(path)
        self.replay_of = replay_of
        self.entries: list[dict] = []
        self.entities: list[dict] = []
        self.snapshots: dict = {}

    def record(self, action: str, kind: str, cost: int = 0, planned: int = None,
               name: str = None, token: str = None, **extra) -> dict:
        entry = {"action": action, "kind": kind, "cost": cost, "planned": planned,
                 "name": name, "token": token, "at": utc_now(), **extra}
        self.entries.append(entry)
        self.save()
        return entry

    def update(self, name: str, **fields) -> dict:
        for entry in self.entries:
            if entry.get("name") == name:
                entry.update(fields)
                self.save()
                return entry
        raise KeyError(f"no ledger entry named {name!r}")

    def find(self, **match) -> list[dict]:
        return [e for e in self.entries
                if all(e.get(k) == v for k, v in match.items())]

    def total_cost(self, kinds=None) -> int:
        return sum(e.get("cost") or 0 for e in self.entries
                   if kinds is None or e.get("kind") in kinds)

    def register_entity(self, kind: str, uid: str, name: str,
                        preserve: bool = False) -> dict:
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
        for entity in self.entities:
            if entity["id"] == uid:
                entity["removed"] = True
        self.save()

    def preserve_all(self):
        """Keeps every entity that exists now as a failed test's evidence."""
        for entity in self.entities:
            entity["preserve"] = True
        self.save()

    def cleanup_targets(self) -> list[dict]:
        return [e for e in self.entities
                if not e.get("preserve") and not e.get("removed")]

    def snapshot(self, key: str, value):
        if key not in self.snapshots:
            self.snapshots[key] = value
            self.save()
        return self.snapshots[key]

    def to_dict(self) -> dict:
        return {"replay_of": self.replay_of, "entries": self.entries,
                "entities": self.entities, "snapshots": self.snapshots}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.to_dict(), indent=2, default=str),
                             encoding="utf-8")

    @classmethod
    def replay(cls, source: Path, path: Path) -> "Ledger":
        prior = json.loads(Path(source).read_text(encoding="utf-8"))
        if not prior.get("entries"):
            raise ValueError(f"{source} records no entries to replay")
        ledger = cls(path, replay_of=str(source))
        ledger.entries = prior["entries"]
        ledger.snapshots = prior.get("snapshots", {})
        ledger.save()
        return ledger
