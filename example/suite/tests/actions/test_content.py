"""A delivered email meets the encoded content standard."""
import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.app_client import UNSUBSCRIBE
from example.suite.flows import wait_until_sent
from framework.delivery.content_checks import (
    assert_chars_survive,
    assert_rendered,
    assert_unsubscribe,
    one_click_url,
)

pytestmark = pytest.mark.pipeline

BODY = ("<p>Hi {{first_name}} {{last_name}},</p>"
        "<p>It's 100% free: save $5 on order #7 &amp; more.</p>")


def test_content_standard(app_api, inbox, config, make_contact, entity_name, subject_token,
                          record, e2e_ledger, checks):
    tag = entity_name("content")
    email = make_contact("content", tags=[tag], first_name="Rosa", last_name="Quill")["email"]
    subject = subject_token("content")
    name = entity_name("content")
    batch = app_api.create_batch(name, f"{subject} for {{{{first_name}}}}", BODY,
                                 audience_tag=tag)
    wait_until_sent(app_api, batch["id"], config.mail_budget_s)
    record("batch.send", kinds.SEND, cost=1, planned=1, name=name, token=subject,
           batch_id=batch["id"], reference=f"batch:{batch['id']}",
           recipients=[email], suppressed=[], opened=[], clicked=[])
    e2e_ledger.register_entity("mail", subject, subject)

    def arrived():
        message = inbox.wait_for(subject=subject, to=email, timeout_s=config.mail_budget_s,
                                 poll_s=2)
        if not message:
            evidence.inbox_listing(checks, inbox, subject, "what the inbox held for this send")
        assert message, f"no copy for {email} within {config.mail_budget_s}s"
        return message
    message = checks.check("the copy arrived", arrived, expected="one copy in the inbox")
    html, headers = inbox.html(message.id), inbox.headers(message.id)

    def on_the_email(check):
        def run():
            evidence.email(checks, inbox, message, "the email as delivered")
            return check()
        return run

    checks.soft_check("template variables rendered", on_the_email(lambda: assert_rendered(
        message.subject, html, {"first_name": "Rosa", "last_name": "Quill"},
        in_subject=["first_name"], in_body=["first_name", "last_name"])),
        expected="the contact's names in subject and body; no literal template variable",
        means="A reader sees a raw template variable or a blank where their name belongs.")
    checks.soft_check("special characters survive",
                      on_the_email(lambda: assert_chars_survive(html)),
                      expected="' , % $ # & all render as typed")
    checks.soft_check("unsubscribe footer and header line",
                      on_the_email(lambda: assert_unsubscribe(html, UNSUBSCRIBE)),
                      expected="the header line and a footer Unsubscribe link")
    widened = "" if config.one_click_schemes == ("https",) else \
        " (http accepted: the local stack is served over http)"
    checks.soft_check("one-click unsubscribe headers",
                      on_the_email(lambda: one_click_url(
                          headers, allowed_schemes=config.one_click_schemes)),
                      expected="List-Unsubscribe with web and mailto entries, and "
                      f"List-Unsubscribe-Post=One-Click{widened}",
                      means="Mail clients will not offer their own one-click unsubscribe.")
    checks.raise_soft_failures()
