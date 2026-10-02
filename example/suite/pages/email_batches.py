import re

from playwright.sync_api import Locator, Page, expect

from example.suite.components.dropdown import RolelessDropdown
from framework.ui.names import label_pattern


class EmailBatchesPage:
    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.goto("/#/email-batches")
        expect(self.page.get_by_role("heading", name="Email batches", exact=True)).to_be_visible()

    def row(self, name: str) -> Locator:
        return self.page.get_by_test_id("batch-row").filter(
            has=self.page.get_by_role("link", name=name, exact=True))

    def status(self, name: str) -> Locator:
        # The badge's text changes in place, so wait on the text.
        return self.row(name).get_by_test_id("status-badge")

    def wait_until_sent(self, name: str, timeout_s: float):
        expect(self.status(name)).to_have_text("Sent", timeout=timeout_s * 1000)

    def new(self) -> "WizardPage":
        self.page.get_by_role("button", name=label_pattern("New email batch")).click()
        wizard = WizardPage(self.page)
        wizard.expect_step(1, "Audience")
        return wizard


class WizardPage:
    def __init__(self, page: Page):
        self.page = page

    def expect_step(self, number: int, title: str):
        expect(self.page.get_by_role("heading", name=re.compile(
            rf"^Step {number} of 4: {title}$"))).to_be_visible()

    def _next(self, number: int, title: str):
        self.page.get_by_role("button", name="Next", exact=True).click()
        self.expect_step(number, title)

    def audience_tag(self, tag: str):
        self.page.get_by_label("Subscribed contacts with a tag").check()
        RolelessDropdown(self.page, "audience-tag").choose(tag)
        self._next(2, "Message")

    def message(self, name: str, subject: str, body_html: str):
        self.page.get_by_label("Email batch name").fill(name)
        self.page.get_by_label("Subject").fill(subject)
        self.page.get_by_label("Message (HTML)").fill(body_html)
        self._next(3, "Address suppression")

    def suppress(self, *list_names: str):
        for name in list_names:
            self.page.get_by_label(re.compile(rf"^{re.escape(name)} \(\d+\)$")).check()
        self._next(4, "Schedule")

    def send_now(self) -> EmailBatchesPage:
        self.page.get_by_label("Send now").check()
        self.page.get_by_role("button", name="Send email batch").click()
        batches = EmailBatchesPage(self.page)
        expect(self.page.get_by_role("heading", name="Email batches", exact=True)).to_be_visible()
        return batches
