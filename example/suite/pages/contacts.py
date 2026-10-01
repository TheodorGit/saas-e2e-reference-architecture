import re
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Locator, Page, expect

from example.suite.components.dialog import ConfirmDialog
from example.suite.components.dropdown import RolelessDropdown
from framework.ui.names import label_pattern


def _lists_contacts(query: dict):
    """Matches the list request carrying exactly these filters."""
    def match(response) -> bool:
        url = urlparse(response.url)
        if url.path != "/api/contacts" or response.request.method != "GET":
            return False
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        return all(params.get(k, "") == v for k, v in query.items())
    return match


class ContactsPage:
    def __init__(self, page: Page):
        self.page = page
        self.table = page.get_by_role("table", name="Contacts")
        self.count = page.get_by_test_id("contacts-count")
        self.tag_filter = RolelessDropdown(page, "tag-filter")

    def open(self):
        self.page.goto("/#/contacts")
        expect(self.count).to_have_text(re.compile(r"^Showing \d+"))

    def _settled(self):
        expect(self.table).not_to_have_attribute("aria-busy", "true")

    # --- reading -----------------------------------------------------------------

    def row(self, email: str) -> Locator:
        return self.page.get_by_test_id("contact-row").filter(
            has=self.page.get_by_role("cell", name=email.lower(), exact=True))

    def emails(self) -> list[str]:
        return [self.row_email(r) for r in self.page.get_by_test_id("contact-row").all()]

    @staticmethod
    def row_email(row: Locator) -> str:
        return row.get_by_role("cell").nth(1).inner_text().strip()

    def tags(self, email: str) -> list[str]:
        return sorted(t.strip() for t in
                      self.row(email).get_by_test_id("tag-chip").all_text_contents())

    # --- filtering ----------------------------------------------------------------

    def search(self, text: str):
        """Type a search. The list reloads only after typing pauses (debounced),
        so this waits for the request carrying THIS query, then for the table."""
        with self.page.expect_response(_lists_contacts({"q": text.strip()})):
            self.page.get_by_placeholder("Search by name or email").fill(text)
        self._settled()

    def filter_tag(self, tag: str):
        with self.page.expect_response(_lists_contacts({"tag": tag})):
            self.tag_filter.choose(tag)
        self._settled()

    # --- acting ---------------------------------------------------------------------

    def add(self, email: str, first_name: str = "", last_name: str = "", tags=()):
        """Ends on the new row. The 'Contact saved' toast renders before the
        request finishes, so it is not the end of this action."""
        self.page.get_by_role("button", name=label_pattern("Add contact")).click()
        form = self.page.get_by_role("form", name="Add contact")
        form.get_by_label("Email").fill(email)
        form.get_by_label("First name").fill(first_name)
        form.get_by_label("Last name").fill(last_name)
        form.get_by_label("Tags").fill(", ".join(tags))
        form.get_by_role("button", name="Save contact").click()
        expect(self.row(email)).to_be_visible()

    def select(self, emails):
        for email in emails:
            self.page.get_by_label(f"Select {email.lower()}", exact=True).check()
        expect(self.page.get_by_test_id("selected-count")).to_have_text(
            f"{len(list(emails))} selected")

    def bulk_tag(self, tag: str, remove: bool = False):
        """Tag or untag the selection. The rows change optimistically (pending)
        and are then re-read from the server: this ends when no pending chip is
        left, i.e. on the server's answer, not the optimistic one."""
        self.page.get_by_label("Tag for selected").fill(tag)
        with self.page.expect_response(lambda r: r.url.endswith("/api/contacts/bulk-tag")):
            self.page.get_by_role("button", name="Remove tag" if remove else "Add tag").click()
        # Pending state is only exposed as a class: CSS is the last resort here.
        expect(self.table.locator("[data-testid=tag-chip].pending")).to_have_count(0)
        self._settled()

    def delete(self, email: str):
        """Ends when the row is gone."""
        row = self.row(email)
        # The button's accessible name is "delete Delete": icon word + label.
        row.get_by_role("button", name=label_pattern("Delete")).click()
        ConfirmDialog(self.page, "Delete contact").confirm("Delete contact")
        expect(row).to_have_count(0)

    def export(self) -> str:
        """Download the CSV export of what the list currently shows."""
        with self.page.expect_download() as caught:
            self.page.get_by_role("link", name="Export CSV").click()
        return open(caught.value.path(), encoding="utf-8").read()
