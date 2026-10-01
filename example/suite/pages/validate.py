from playwright.sync_api import Page, expect


class ValidatePage:
    def __init__(self, page: Page):
        self.page = page
        self.result = page.get_by_test_id("validation-result")

    def open(self):
        self.page.goto("/#/validate")
        expect(self.page.get_by_role("heading", name="Validate an address")).to_be_visible()

    def validate(self, email: str) -> dict:
        """Validate one address. Ends on the result for THIS request: the previous
        result may carry identical text, so the response is awaited first."""
        self.page.get_by_label("Email address").fill(email)
        with self.page.expect_response(lambda r: r.url.endswith("/api/validate")) as caught:
            self.page.get_by_role("button", name="Validate address").click()
        response = caught.value
        expect(self.result).to_be_visible()
        expect(self.result).to_contain_text(email.lower())
        return {"charge": self.page.get_by_test_id("validation-charge").inner_text(),
                "status": response.status, "body": response.json()}
