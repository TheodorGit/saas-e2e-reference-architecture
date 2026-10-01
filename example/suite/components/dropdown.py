"""The app's custom dropdown, which exposes NO ARIA roles.

There is no combobox, listbox or option to find by role, and the placeholder
text appears twice (the toggle and the first, hidden, menu item), so text alone
is ambiguous. The container has a test id; inside it, the toggle and items are
reached by class - CSS as the last resort, because nothing else identifies them.
"""
import re

from playwright.sync_api import Locator, Page, expect


class RolelessDropdown:
    def __init__(self, page: Page, test_id: str):
        self.root = page.get_by_test_id(test_id)
        self.toggle = self.root.locator(".dropdown-toggle")
        self.menu = self.root.locator(".dropdown-menu")

    def _item(self, text: str) -> Locator:
        return self.menu.locator(".dropdown-item").filter(
            has_text=re.compile(rf"^{re.escape(text)}$"))

    def choose(self, option: str):
        """Pick an option; ends when the toggle shows it and the menu is closed."""
        self.toggle.click()
        expect(self.menu).to_be_visible()
        self._item(option).click()
        expect(self.toggle).to_have_text(option)
        expect(self.menu).to_be_hidden()

    def options(self) -> list[str]:
        """Every option offered, read with the menu open, then closed again."""
        self.toggle.click()
        expect(self.menu).to_be_visible()
        texts = [t.strip() for t in self.menu.locator(".dropdown-item").all_text_contents()]
        self.toggle.click()
        expect(self.menu).to_be_hidden()
        return texts
