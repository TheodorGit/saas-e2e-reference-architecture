"""A contact's whole life through the public API."""
import pytest

from example.suite import ledger_kinds as kinds

pytestmark = pytest.mark.api


def test_api_contact_lifecycle(v1, config, entity_name, e2e_ledger, record):
    token = entity_name("api")
    sent = {"email": config.address(token), "first_name": "Api", "last_name": "Reader",
            "tags": [token]}
    created = v1.call("POST", "/v1/contacts", expect=201, json=sent)
    if created is None or created.status_code != 201:
        return  # the failed call is recorded; teardown fails the test
    contact = created.json()
    e2e_ledger.register_entity("contact", contact["id"], contact["email"])
    record("contact.add", kinds.CONTACT, name=token, email=contact["email"],
           contacts_delta=1, subscribed_delta=1)

    v1.check("created as sent", lambda: _as_sent(contact, sent),
             expected="email, names and tags exactly as sent, status subscribed",
             means="The API stores something other than what the client sent.")
    read = v1.call("GET", "/v1/contacts/{contact_id}", contact_id=contact["id"])
    v1.check("read back unchanged", lambda: _same(read.json(), contact),
             expected="the single-contact read equals what creation returned")
    listed = v1.call("GET", "/v1/contacts", params={"tag": token})
    v1.check("found by its tag", lambda: _emails(listed.json()) == [contact["email"]]
             or _fail(f"tag filter returned {_emails(listed.json())}"),
             expected="the tag filter returns exactly this contact")

    v1.call("POST", "/v1/contacts", expect=400, name="a duplicate is refused", json=sent)
    v1.call("POST", "/v1/contacts", expect=400, name="a malformed address is refused",
            json={**sent, "email": "not-an-address"})

    deleted = v1.call("DELETE", "/v1/contacts/{contact_id}", contact_id=contact["id"])
    if deleted is not None and deleted.status_code == 200:
        e2e_ledger.mark_removed(contact["id"])
        record("contact.delete", kinds.CONTACT, name=f"{token}-delete",
               email=contact["email"], contacts_delta=-1, subscribed_delta=-1)
    v1.call("GET", "/v1/contacts/{contact_id}", expect=404, name="gone after delete",
            contact_id=contact["id"])


def _as_sent(contact: dict, sent: dict):
    got = {k: contact[k] for k in ("email", "first_name", "last_name", "tags")}
    want = {**sent, "email": sent["email"].lower()}
    assert got == want and contact["status"] == "subscribed", f"stored {got}, sent {want}"


def _same(read: dict, created: dict):
    assert read == created, f"read {read}, created {created}"


def _emails(listing: dict) -> list[str]:
    return [c["email"] for c in listing["items"]]


def _fail(message: str):
    raise AssertionError(message)
