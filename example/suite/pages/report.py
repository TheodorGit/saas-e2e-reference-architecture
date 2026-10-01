from playwright.sync_api import Page, expect

from example.suite.components.numbers import painted_number

# card key -> heading of its drill-down list
DRILLDOWNS = {"delivered": "Delivered to", "opens": "Opened by", "clicks": "Clicked by"}


class ReportPage:
    def __init__(self, page: Page):
        self.page = page
        self.drilldown = page.get_by_test_id("drilldown")

    def open(self, batch_id: int, name: str):
        self.page.goto(f"/#/email-batches/{batch_id}")
        expect(self.page.get_by_role("heading", name=name, exact=True)).to_be_visible()

    def card(self, key: str) -> int:
        """The card's number, once painted (the label paints first)."""
        return painted_number(self.page.get_by_test_id(f"card-value-{key}"))

    def drill(self, key: str) -> list[str]:
        """Open the card's list of WHO; ends on the list (or its empty state)."""
        heading = DRILLDOWNS[key]
        self.page.get_by_test_id(f"card-{key}").click()
        expect(self.drilldown.get_by_role("heading", name=heading)).to_be_visible()
        people = self.drilldown.get_by_role("list", name=heading)
        if people.count() == 0:
            expect(self.drilldown.get_by_text("Nobody yet.")).to_be_visible()
            return []
        return sorted(t.strip().lower() for t in people.get_by_role("listitem").all_inner_texts())
