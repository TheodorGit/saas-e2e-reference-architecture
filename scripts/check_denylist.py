"""Refuse any file that matches a denylist of identifiers that must never be committed.

A suite that tests a real product touches real identifiers: the product's domains
and hosts, account and customer ids, people's names and addresses. The denylist
holds the ones that must never reach a repository - the product's, and any
client's. It lives OUTSIDE the repo so it can never be committed itself:

    E2E_DENYLIST=<path>          explicit location, or
    ~/.saas-e2e-denylist.txt     the default

One regex per line, matched case-insensitively. Blank lines and lines starting
with '#' are ignored.

Usage:
    python scripts/check_denylist.py <file> [<file> ...]   # pre-commit passes staged files
    python scripts/check_denylist.py --all                 # every git-tracked file

A missing denylist is a FAILURE, never a pass: a guard that silently does
nothing is worse than no guard.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_PATH = Path.home() / ".saas-e2e-denylist.txt"
SELF = Path(__file__).resolve()


def load_patterns(path: Path) -> list[tuple[int, re.Pattern]]:
    patterns = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append((number, re.compile(line, re.IGNORECASE)))
        except re.error as exc:
            sys.exit(f"denylist line {number} is not a valid regex: {exc}")
    return patterns


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f]


def read_text(path: Path):
    """File contents as text, or None for binary or unreadable files."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def scan(files: list[str], patterns) -> list[str]:
    hits = []
    for name in files:
        path = Path(name)
        if path.resolve() == SELF:
            continue
        # The path itself can leak an identifier too.
        for number, pattern in patterns:
            if pattern.search(name.replace("\\", "/")):
                hits.append(f"{name}: path matches denylist line {number}")
        text = read_text(path)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for number, pattern in patterns:
                if pattern.search(line):
                    hits.append(f"{name}:{line_no}: matches denylist line {number}")
    return hits


def main(argv: list[str]) -> int:
    path = Path(os.environ.get("E2E_DENYLIST") or DEFAULT_PATH)
    if not path.is_file():
        print(f"denylist not found at {path}. Create it (see this script's "
              f"docstring) or set E2E_DENYLIST. Refusing to pass without it.")
        return 1
    patterns = load_patterns(path)
    if not patterns:
        print(f"denylist at {path} holds no patterns. Refusing to pass without any.")
        return 1

    files = tracked_files() if argv == ["--all"] else argv
    hits = scan(files, patterns)
    if hits:
        print("Denylisted content found - remove it before committing:")
        for hit in hits:
            print(f"  {hit}")
        return 1
    print(f"denylist: {len(files)} file(s) clean against {len(patterns)} pattern(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
