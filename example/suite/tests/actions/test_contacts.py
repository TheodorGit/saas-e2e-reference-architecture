"""Contacts through the UI, each proven on the API."""
import csv
import io

import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.pages.contacts import ContactsPage
from framework.pipeline.sets import assert_same

pytestmark = pytest.mark.pipeline


def _emails(contacts) -> list[str]:
    return [c["email"] for c in contacts]


def test_add_contact(app_page, app_api, config, entity_name, e2e_ledger, record, steps):
    token = entity_name("add")
    email = config.address(token)
    page = ContactsPage(app_page)
    page.open()
    steps.step("add through the form",
               lambda: page.add(email, "Ada", "Tester", tags=[token]),
               expected="the new row in the list - not just the 'saved' toast, which "
                        "renders before the request finishes", ui=True)

    def stored():
        contact = app_api.contact(email)
        evidence.data(steps, "what the API holds for this address", contact)
        assert contact, f"the API has no contact {email}"
        return contact
    contact = steps.step("the API has it", stored, expected="the contact exists server-side")
    e2e_ledger.register_entity("contact", contact["id"], email)
    record("contact.add", kinds.CONTACT, name=token, email=email, contacts_delta=1,
           subscribed_delta=1)

    def fields():
        evidence.data(steps, "the contact the API returned", contact)
        got = (contact["first_name"], contact["last_name"], contact["status"], contact["tags"])
        assert got == ("Ada", "Tester", "subscribed", [token]), f"stored as {got}"
    steps.step("fields stored as entered", fields,
               expected="names, tag and a subscribed status, exactly as entered")


def test_ui_delete(app_page, app_api, make_contact, e2e_ledger, record, steps):
    contact = make_contact("delete")
    page = ContactsPage(app_page)
    page.open()
    page.search(contact["email"])
    steps.step("delete through the UI", lambda: page.delete(contact["email"]),
               expected="the row is gone after confirming in the dialog", ui=True)
    e2e_ledger.mark_removed(contact["id"])
    record("contact.delete", kinds.CONTACT, name=f"delete-{contact['id']}",
           email=contact["email"], contacts_delta=-1, subscribed_delta=-1)

    def gone():
        still = app_api.contact(contact["email"])
        evidence.data(steps, "what the API holds for this address", still)
        assert still is None, "the API still has the contact"
    steps.step("the API no longer has it", gone, expected="deleted server-side")


def test_bulk_tag_live_refresh(app_page, app_api, make_contact, entity_name, steps):
    group = entity_name("bulk")
    people = _emails(make_contact(f"bulk{i}", tags=[group]) for i in range(3))
    chosen, other = people[:2], people[2]
    extra = f"{group}-vip"

    page = ContactsPage(app_page)
    page.open()
    page.filter_tag(group)
    steps.step("filter by the group's tag", lambda: assert_same(people, page.emails(),
                                                                "listed contacts"),
               expected="exactly the three run contacts are listed", ui=True)

    page.select(chosen)
    steps.step("bulk add a tag", lambda: page.bulk_tag(extra),
               expected="the optimistic (pending) chips are replaced by the server's list",
               ui=True)

    def shown(expected_holders):
        holders = [e for e in people if extra in page.tags(e)]
        # Empty is the point once the tag is removed.
        return assert_same(expected_holders, holders, f"rows showing {extra}",
                           allow_empty=not expected_holders)
    steps.step("the list shows the server's truth", lambda: shown(chosen),
               expected=f"the two chosen rows carry the tag, {other} does not", ui=True)
    def api_holders(expected_holders):
        holders = _emails(app_api.contacts(tag=extra))
        evidence.data(steps, f"the contacts the API has tagged {extra}", holders)
        return assert_same(expected_holders, holders, f"contacts tagged {extra}",
                           allow_empty=not expected_holders)
    steps.step("the API agrees", lambda: api_holders(chosen),
               expected="exactly the two chosen contacts carry the tag server-side")
    steps.step("the tag filter offers the new tag",
               lambda: _offered(page.tag_filter.options(), extra),
               expected="the filter's options were re-read from the server", ui=True)

    steps.step("bulk remove the tag", lambda: page.bulk_tag(extra, remove=True),
               expected="the list re-reads from the server after removing", ui=True)
    steps.step("no row shows it any more", lambda: shown([]),
               expected="no row carries the removed tag", ui=True)
    steps.step("the API agrees again", lambda: api_holders([]),
               expected="no contact carries the tag server-side")


def _offered(options: list[str], tag: str):
    assert tag in options, f"{tag!r} not offered; options are {options}"


def test_export_follows_the_filter(app_page, app_api, make_contact, entity_name, steps):
    group = entity_name("export")
    inside = _emails(make_contact(f"exp-in{i}", tags=[group]) for i in range(2))
    make_contact("exp-out")

    page = ContactsPage(app_page)
    page.open()
    page.filter_tag(group)
    exported = steps.step("export the filtered list", page.export,
                          expected="a CSV download", ui=True)

    def matches():
        rows = list(csv.DictReader(io.StringIO(exported)))
        filtered = _emails(app_api.contacts(tag=group))
        steps.attach("the exported file", exported, "csv")
        evidence.data(steps, f"the contacts the API has tagged {group}", filtered)
        assert_same(filtered, [r["email"] for r in rows],
                    "exported contacts")
        return f"{len(rows)} rows, exactly the filtered contacts"
    steps.step("the export holds exactly the filtered contacts", matches,
               expected=f"the {len(inside)} contacts tagged {group}, and no one else")
