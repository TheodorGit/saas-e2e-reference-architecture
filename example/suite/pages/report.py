from playwright.sync_api import Page, expect

DRILLDOWNS = {"delivered": "Delivered to", "opens": "Opened by", "clicks": "Clicked by"}


class ReportPage:
    def __init__(self, page: Page):
        self.page = page
        self.drilldown = page.get_by_test_id("drilldown")

    def open(self, batch_id: int, name: str):
        self.page.goto(f"/#/email-batches/{batch_id}")
        expect(self.page.get_by_role("heading", name=name, exact=True)).to_be_visible()

    def expect_card(self, key: str, number: int):
        expect(self.page.get_by_test_id(f"card-value-{key}")).to_have_text(f"{number:,}")

    def drill(self, key: str) -> list[str]:
        heading = DRILLDOWNS[key]
        self.page.get_by_test_id(f"card-{key}").click()
        expect(self.drilldown.get_by_role("heading", name=heading)).to_be_visible()
        people = self.drilldown.get_by_role("list", name=heading)
        empty = self.drilldown.get_by_text("Nobody yet.")
        # A drill-down shows a list or the empty note; read it once one of them is there.
        expect(people.or_(empty).first).to_be_visible()
        if people.count() == 0:
            expect(empty).to_be_visible()
            return []
        return sorted(t.strip().lower() for t in people.get_by_role("listitem").all_inner_texts())
