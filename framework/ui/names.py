"""Accessible names that carry an icon word."""
import re

ICON_WORD = r"[a-z][a-z0-9_]*"


def label_pattern(label: str) -> re.Pattern:
    return re.compile(rf"^(?:{ICON_WORD}\s+)?{re.escape(label)}$")
