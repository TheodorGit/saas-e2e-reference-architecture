from playwright.sync_api import Page, expect


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.goto("/#/login")
        expect(self.page.get_by_role("heading", name="Sign in to Demo ESP App")).to_be_visible()

    def _submit(self, email: str, password: str):
        self.page.get_by_label("Email").fill(email)
        self.page.get_by_label("Password").fill(password)
        self.page.get_by_role("button", name="Sign in").click()

    def sign_in(self, email: str, password: str):
        """Ends on the dashboard."""
        self._submit(email, password)
        expect(self.page.get_by_role("heading", name="Dashboard")).to_be_visible()

    def sign_in_refused(self, email: str, password: str) -> str:
        """Ends on the error message, still on the login screen; returns it."""
        self._submit(email, password)
        alert = self.page.get_by_role("alert")
        expect(alert).not_to_be_empty()
        expect(self.page.get_by_role("heading", name="Sign in to Demo ESP App")).to_be_visible()
        return alert.inner_text()
