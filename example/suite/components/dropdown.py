"""The app's custom dropdown, which has no ARIA roles."""
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
        self.toggle.click()
        expect(self.menu).to_be_visible()
        self._item(option).click()
        expect(self.toggle).to_have_text(option)
        expect(self.menu).to_be_hidden()

    def options(self) -> list[str]:
        self.toggle.click()
        expect(self.menu).to_be_visible()
        texts = [t.strip() for t in self.menu.locator(".dropdown-item").all_text_contents()]
        self.toggle.click()
        expect(self.menu).to_be_hidden()
        return texts
