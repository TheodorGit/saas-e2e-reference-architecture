from playwright.sync_api import Page, expect

from example.suite.components.numbers import painted_number

PANELS = ("credits", "contacts", "subscribed", "batches_sent")


class DashboardPage:
    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.goto("/#/dashboard")
        expect(self.page.get_by_role("heading", name="Dashboard")).to_be_visible()

    def refresh(self):
        """Re-read from the server. goto() to the same #/dashboard is a same-document
        navigation: the view is not rebuilt and would keep showing old numbers."""
        self.page.reload()
        expect(self.page.get_by_role("heading", name="Dashboard")).to_be_visible()

    def value(self, key: str) -> int:
        """The panel's number, once painted (the label paints first)."""
        return painted_number(self.page.get_by_test_id(f"value-{key}"))

    def values(self) -> dict:
        return {key: self.value(key) for key in PANELS}
