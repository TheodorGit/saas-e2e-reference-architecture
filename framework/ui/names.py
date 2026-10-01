"""Accessible names polluted by icon ligatures.

Icon fonts render a WORD ("delete", "person_add") as a glyph. Unless the icon is
hidden from assistive tech, that word is part of the button's accessible name:
"delete Delete". An exact role locator for "Delete" then finds nothing, and a
substring match finds too much ("Delete contact", "Undelete").

`label_pattern` matches the name by its visible label at the END, allowing any
single icon word in front of it, and nothing else.
"""
import re

ICON_WORD = r"[a-z][a-z0-9_]*"


def label_pattern(label: str) -> re.Pattern:
    """Matches 'label' or '<icon_word> label', exactly."""
    return re.compile(rf"^(?:{ICON_WORD}\s+)?{re.escape(label)}$")
