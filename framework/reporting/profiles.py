"""Suite profiles: how a suite presents itself in the report."""
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

Facts = Callable[[Path, list], list]


@dataclass
class SuiteProfile:
    key: str
    path_prefix: str
    title: str
    sections: list = field(default_factory=list)
    titles: dict = field(default_factory=dict)
    facts: Facts = None
    passed_subhead: str = "Every test below ran end to end."

    def section_for(self, func: str) -> str:
        for section, funcs in self.sections:
            if func in funcs:
                return section
        return "Other"

    def title_for(self, func: str) -> str:
        return self.titles.get(func, func)

    def number_for(self, func: str) -> int:
        ordered = [f for _, funcs in self.sections for f in funcs]
        return ordered.index(func) + 1 if func in ordered else 0


GENERIC = SuiteProfile(key="generic", path_prefix="", title="Test run")

_REGISTRY: dict[str, SuiteProfile] = {}


def register(profile: SuiteProfile) -> SuiteProfile:
    _REGISTRY[profile.key] = profile
    return profile


def registered() -> list[SuiteProfile]:
    return list(_REGISTRY.values())


def clear():
    _REGISTRY.clear()


def profile_for(nodeid: str) -> SuiteProfile:
    path = (nodeid or "").replace("\\", "/")
    matches = [p for p in _REGISTRY.values() if path.startswith(p.path_prefix)]
    return max(matches, key=lambda p: len(p.path_prefix)) if matches else GENERIC
