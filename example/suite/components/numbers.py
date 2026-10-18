"""Numbers that paint after their label."""
import re

from playwright.sync_api import Locator, expect

NUMBER = re.compile(r"^\d[\d,]*$")


def painted_number(value: Locator) -> int:
    # The label paints before the number, so wait for a number.
    expect(value).to_have_text(NUMBER)
    return int(value.inner_text().replace(",", ""))
