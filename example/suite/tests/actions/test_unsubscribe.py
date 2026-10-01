"""Unsubscribing and resubscribing, the way a recipient does it: from the email.

One recipient uses the public page linked in the footer, then resubscribes; the
other uses RFC 8058 one-click, as a mail client would. Each status change is
proven on the API. Whether an unsubscribe is miscounted as engagement is verified
later, once stats have landed.
"""
import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.app_client import TRACKERS
from example.suite.flows import body_with_link, wait_until_sent
from example.suite.pages.preferences import PreferencesPage
from framework.delivery.content_checks import list_unsubscribe_targets
from framework.delivery.links import engage, find_unsubscribe_link
from framework.delivery.one_click import post_one_click

pytestmark = pytest.mark.pipeline


def _status_is(api, email: str, status: str, steps):
    found = api.contact(email)
    evidence.data(steps, "what the API holds for this address", found)
    assert found, f"the API has no contact {email}"
    assert found["status"] == status, f"{email} is {found['status']!r}, expected {status!r}"
    return status


def test_unsubscribe_and_resubscribe(anon_page, app_api, inbox, config, make_contact,
                                     entity_name, subject_token, record, e2e_ledger, steps):
    tag = entity_name("unsub")
    by_page = make_contact("unsub-page", tags=[tag], first_name="Paige")["email"]
    by_click = make_contact("unsub-oneclick", tags=[tag], first_name="Cliff")["email"]
    recipients = sorted([by_page, by_click])
    subject = subject_token("unsub")
    name = entity_name("unsub")
    batch = app_api.create_batch(name, f"{subject} for {{{{first_name}}}}",
                                 body_with_link(config.base_url), audience_tag=tag)
    wait_until_sent(app_api, batch["id"], config.mail_budget_s)
    entry = record("batch.send", kinds.UNSUBSCRIBE_SEND, cost=2, planned=2, name=name,
                   token=subject, batch_id=batch["id"],
                   reference=f"batch:{batch['id']}", recipients=recipients,
                   unsubscribed=[], one_click=[], opened=[])
    e2e_ledger.register_entity("mail", subject, subject)

    def arrived():
        found = inbox.wait_for_each(subject, recipients, timeout_s=config.mail_budget_s,
                                    poll_s=2)
        missing = sorted(set(recipients) - set(found))
        if missing:
            evidence.inbox_listing(steps, inbox, subject, "what the inbox held for this send")
        assert not missing, f"no copy within {config.mail_budget_s}s for {missing}"
        return found
    copies = steps.step("both copies arrived", arrived, expected="one copy each")

    # --- the public page, from the footer link --------------------------------------
    link = find_unsubscribe_link(inbox.html(copies[by_page].id), anchor_texts=("Unsubscribe",))
    prefs = PreferencesPage(anon_page)
    steps.step("open the footer link", lambda: prefs.open(link),
               expected="the public preferences page, no sign-in needed", ui=True)
    # Each change is recorded once the API confirms it: a page can confirm a
    # change the system never made, and the ledger must not believe it.
    steps.step("unsubscribe on the page", prefs.unsubscribe,
               expected="the page confirms and shows the address unsubscribed", ui=True)
    steps.step("the API shows it unsubscribed",
               lambda: _status_is(app_api, by_page, "unsubscribed", steps),
               expected="status unsubscribed server-side")
    record("contact.unsubscribe", kinds.STATUS, name=f"unsub-{by_page}", email=by_page,
           subscribed_delta=-1)
    steps.step("resubscribe on the same page", prefs.resubscribe,
               expected="the page confirms and shows the address subscribed", ui=True)
    steps.step("the API shows it subscribed again",
               lambda: _status_is(app_api, by_page, "subscribed", steps),
               expected="status subscribed server-side",
               means="The page confirmed a resubscribe the system did not save.")
    record("contact.resubscribe", kinds.STATUS, name=f"resub-{by_page}", email=by_page,
           subscribed_delta=1)

    # --- one-click, as a mail client does it -------------------------------------------
    def one_click():
        targets = list_unsubscribe_targets(inbox.headers(copies[by_click].id))
        url = next((t for t in targets if t.startswith(("https://", "http://"))), None)
        assert url, f"no web URL in List-Unsubscribe: {targets}"
        answer = post_one_click(url)
        evidence.data(steps, "the one-click answer", {"url": url, **answer})
        assert answer["status_code"] == 200, f"one-click answered {answer}"
        return answer.get("status")
    steps.step("one-click POST", one_click,
               expected="the List-Unsubscribe URL accepts List-Unsubscribe=One-Click")
    steps.step("the API shows it unsubscribed",
               lambda: _status_is(app_api, by_click, "unsubscribed", steps),
               expected="status unsubscribed server-side")
    record("contact.unsubscribe", kinds.STATUS, name=f"oneclick-{by_click}", email=by_click,
           subscribed_delta=-1)

    # --- a marker the run owns, fired AFTER the unsubscribes -----------------------------
    def marker():
        fired = engage(inbox, {by_page: copies[by_page]}, TRACKERS, open_mail=True)
        assert not fired["failures"], "; ".join(fired["failures"])
        return fired["opened"]
    opened = steps.step("fire a marker open after the unsubscribes", marker,
                        expected="once this open is in the report, so are the unsubscribes")
    e2e_ledger.update(entry["name"], unsubscribed=recipients, one_click=[by_click],
                      opened=opened)
