"""The in-page confirmation dialog."""
from playwright.sync_api import Page, expect

from framework.ui.names import label_pattern


class ConfirmDialog:
    def __init__(self, page: Page, title: str):
        self.dialog = page.get_by_role("dialog", name=title)

    def confirm(self, button: str):
        """Press the confirming button; ends when the dialog is gone."""
        expect(self.dialog).to_be_visible()
        # The button's accessible name carries its icon word ("delete Delete contact").
        self.dialog.get_by_role("button", name=label_pattern(button)).click()
        expect(self.dialog).to_be_hidden()
