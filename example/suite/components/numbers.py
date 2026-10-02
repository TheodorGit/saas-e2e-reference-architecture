"""Numbers that paint after their label."""
import re

from playwright.sync_api import Locator, expect

NUMBER = re.compile(r"^\d[\d,]*$")


def painted_number(value: Locator, timeout: float = 15_000) -> int:
    # The label paints before the number, so wait for a number.
    expect(value).to_have_text(NUMBER, timeout=timeout)
    return int(value.inner_text().replace(",", ""))
