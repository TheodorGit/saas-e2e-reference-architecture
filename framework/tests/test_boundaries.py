"""The framework stays product-agnostic.

These are the rules that make framework/ a reference architecture rather than
one product's test code: it never reaches into example/, and product meaning
reaches it only through its documented seams, never as hardcoded vocabulary.
"""
import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

FRAMEWORK = Path(__file__).resolve().parent.parent

# Words that belong to the example product. The framework talks about runs,
# steps, sends, recipients and ledger entries; it never names a product feature.
PRODUCT_WORDS = re.compile(
    r"\b(broadcasts?|campaigns?|credits?|demo[ _-]?esp|newsletters?|email[ _-]?batch(es)?|"
    r"automations?)\b", re.IGNORECASE)


def _sources():
    return [p for p in FRAMEWORK.rglob("*.py") if p.resolve() != Path(__file__).resolve()]


def test_framework_never_imports_the_example():
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [f"{path.relative_to(FRAMEWORK)}: imports {n}"
                          for n in names if n == "example" or n.startswith("example.")]
    assert not offenders, "framework/ must not import example/:\n" + "\n".join(offenders)


def test_framework_uses_no_product_vocabulary():
    offenders = []
    for path in _sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = PRODUCT_WORDS.search(line)
            if match:
                offenders.append(f"{path.relative_to(FRAMEWORK)}:{number}: {match.group(0)!r}")
    assert not offenders, (
        "framework/ names product features; move the meaning behind a seam:\n"
        + "\n".join(offenders))


def test_framework_source_is_ascii():
    offenders = []
    for path in _sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.isascii():
                offenders.append(f"{path.relative_to(FRAMEWORK)}:{number}")
    assert not offenders, "non-ASCII characters in framework/:\n" + "\n".join(offenders)
