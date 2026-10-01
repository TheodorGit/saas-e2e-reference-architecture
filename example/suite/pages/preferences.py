from playwright.sync_api import Page, expect


class PreferencesPage:
    """The public unsubscribe/resubscribe page a recipient reaches from an email."""

    def __init__(self, page: Page):
        self.page = page
        self.state = page.get_by_test_id("subscription-state")

    def open(self, url: str):
        self.page.goto(url)
        expect(self.page.get_by_role("heading", name="Email preferences")).to_be_visible()

    def unsubscribe(self):
        """Ends on the confirmation and the unsubscribed state."""
        self.page.get_by_role("button", name="Unsubscribe", exact=True).click()
        expect(self.page.get_by_role("status")).to_have_text("You have been unsubscribed.")
        expect(self.state).to_contain_text("is unsubscribed")

    def resubscribe(self):
        """Ends on the confirmation and the subscribed state."""
        self.page.get_by_role("button", name="Resubscribe", exact=True).click()
        expect(self.page.get_by_role("status")).to_contain_text("subscribed again")
        expect(self.state).to_contain_text("You are subscribed as")
