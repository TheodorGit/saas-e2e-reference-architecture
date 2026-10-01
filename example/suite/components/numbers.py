"""Numbers that paint after their label."""
import re

from playwright.sync_api import Locator, expect

NUMBER = re.compile(r"^\d[\d,]*$")


def painted_number(value: Locator, timeout: float = 15_000) -> int:
    """Wait until `value` shows a number (not its placeholder) and return it.
    Reading as soon as the label is visible reads the placeholder."""
    expect(value).to_have_text(NUMBER, timeout=timeout)
    return int(value.inner_text().replace(",", ""))
