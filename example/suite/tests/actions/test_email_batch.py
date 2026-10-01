"""An email batch through the wizard, to a tag, with an address suppression list.

The suppressed contact is IN the audience, so only the suppression list can keep
it out. The positive control is an ordinary recipient: its copy arriving proves
the send happened, which is what makes the suppressed contact's empty inbox mean
something.
"""
import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.app_client import TRACKERS
from example.suite.flows import body_with_link
from example.suite.pages.email_batches import EmailBatchesPage
from framework.delivery.links import engage
from framework.pipeline.sets import assert_same
from framework.safety.guards import assert_owned, assert_within_cap

pytestmark = pytest.mark.pipeline


def test_email_batch_send_with_suppression(app_page, app_api, inbox, config, run_id,
                                           entity_name, subject_token, make_contact,
                                           make_suppression, record, e2e_ledger, steps):
    tag = entity_name("audience")
    # Created first, so it would be the first message sent if it leaked.
    held = make_contact("held", tags=[tag], first_name="Held")["email"]
    reader = make_contact("reader", tags=[tag], first_name="Reader")["email"]
    control = make_contact("control", tags=[tag], first_name="Control")["email"]
    suppression = make_suppression("suppress", [held])
    expected = sorted([reader, control])

    audience = [c["email"] for c in app_api.contacts(tag=tag) if c["status"] == "subscribed"]
    steps.step("the audience is exactly the three contacts made here",
               lambda: assert_same([held, reader, control], audience, "audience"),
               expected="held, reader and control - no one more, no one less")
    steps.step("audience within the cap",
               lambda: assert_within_cap(len(audience), config.audience_cap),
               expected=f"at most {config.audience_cap} members")
    steps.step("audience is ours",
               lambda: assert_owned(audience, lambda a: config.is_ours(a, run_id)),
               expected="every member is a run-owned alias")

    subject = subject_token("send")
    name = entity_name("batch")
    wizard = EmailBatchesPage(app_page)
    wizard.open()
    wizard = wizard.new()
    wizard.audience_tag(tag)
    wizard.message(name, f"{subject} for {{{{first_name}}}}", body_with_link(config.base_url))
    wizard.suppress(suppression["name"])
    listing = wizard.send_now()
    steps.step("the list shows it sent",
               lambda: listing.wait_until_sent(name, config.mail_budget_s),
               expected="the row's status badge changes its text to Sent, in place", ui=True)

    batch = app_api.batch_named(name)
    entry = record("batch.send", kinds.SEND, cost=len(expected), planned=len(expected),
                   name=name, token=subject, batch_id=batch["id"],
                   reference=f"batch:{batch['id']}", recipients=expected,
                   suppressed=[held], opened=[], clicked=[])
    e2e_ledger.register_entity("mail", subject, subject)

    def arrived():
        copies = inbox.wait_for_each(subject, expected, timeout_s=config.mail_budget_s,
                                     poll_s=2)
        missing = sorted(set(expected) - set(copies))
        if missing:
            evidence.inbox_listing(steps, inbox, subject, "what the inbox held for this send")
        assert not missing, f"no copy within {config.mail_budget_s}s for {missing}"
        return copies
    copies = steps.step("each recipient's own copy arrived", arrived,
                        expected=f"{len(expected)} copies, one per recipient")

    def held_back():
        # Sent means every message was handed to SMTP, and the control's arrived.
        leaked = inbox.search(subject=subject, to=held)
        for message in leaked:
            evidence.email(steps, inbox, message, "the email they received")
        assert not leaked, f"the suppressed contact {held} received the email batch"
    steps.step("the suppressed contact got nothing", held_back,
               expected="no copy for the suppressed address, while the control's arrived",
               means="An address suppression list did not keep its addresses out of a send.")

    def engaged():
        opened = engage(inbox, copies, TRACKERS, open_mail=True)
        clicked = engage(inbox, {reader: copies[reader]}, TRACKERS, open_mail=False,
                         click_text="Read more")
        failures = opened["failures"] + clicked["failures"]
        assert not failures, "; ".join(failures)
        e2e_ledger.update(entry["name"], opened=opened["opened"], clicked=clicked["clicked"])
        return f"opened {len(opened['opened'])}, clicked {len(clicked['clicked'])}"
    steps.step("engage: both open, the reader clicks", engaged,
               expected="every pixel and tracked link answered; who was engaged is recorded")
