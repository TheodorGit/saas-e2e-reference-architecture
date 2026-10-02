"""An automation: adding a tag starts a delayed email, and an unsubscribed contact gets nothing."""
from datetime import datetime

import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.flows import body_with_link
from framework.pipeline.sets import assert_same
from framework.polling import poll_until
from framework.safety.guards import assert_owned

pytestmark = pytest.mark.pipeline

DELAY_S = 5
OPEN = ("waiting", "sending")


def test_automation_skips_unsubscribed(app_api, inbox, config, run_id, entity_name,
                                       subject_token, make_contact, record, e2e_ledger,
                                       steps):
    reader = make_contact("auto-reader", first_name="Reader")
    gone = make_contact("auto-gone", first_name="Gone", status="unsubscribed")
    people = [reader["email"], gone["email"]]
    steps.step("both contacts are ours",
               lambda: assert_owned(people, lambda a: config.is_ours(a, run_id)),
               expected="every contact the trigger will reach is a run-owned alias")

    trigger = entity_name("trigger")
    subject = subject_token("automation")
    automation = app_api.create_automation(entity_name("automation"), trigger, DELAY_S,
                                           f"{subject} for {{{{first_name}}}}",
                                           body_with_link(config.base_url))
    e2e_ledger.register_entity("automation", automation["id"], automation["name"])
    e2e_ledger.register_entity("mail", subject, subject)

    app_api.bulk_tag([reader["id"], gone["id"]], trigger)

    def enrolled():
        runs = app_api.automation(automation["id"])["runs"]
        evidence.data(steps, "the automation's runs", runs)
        return assert_same(people, [r["email"] for r in runs], "contacts enrolled")
    steps.step("adding the tag enrolled both contacts", enrolled,
               expected="one run per contact the trigger tag was added to")

    def finished():
        runs, waited = poll_until(lambda: app_api.automation(automation["id"])["runs"],
                                  lambda rs: all(r["status"] not in OPEN for r in rs),
                                  DELAY_S + config.mail_budget_s, 1)
        evidence.data(steps, "the automation's runs", runs)
        still = [r["email"] for r in runs if r["status"] in OPEN]
        assert not still, f"still waiting after {waited:.0f}s: {still}"
        return {r["email"]: r for r in runs}
    runs = steps.step("the delay ran out and both runs finished", finished,
                      expected=f"after the {DELAY_S}s delay, each run is sent or skipped")
    record("automation.send", kinds.AUTOMATION, name=automation["name"], token=subject,
           automation_id=automation["id"], recipients=[reader["email"]],
           held=[gone["email"]])

    def arrived():
        message = inbox.wait_for(subject=subject, to=reader["email"],
                                 timeout_s=config.mail_budget_s, poll_s=2)
        if not message:
            evidence.inbox_listing(steps, inbox, subject, "what the inbox held for this send")
        assert message, f"no copy for {reader['email']} within {config.mail_budget_s}s"
    steps.step("the subscribed contact's copy arrived", arrived,
               expected="their own copy, in the inbox")

    def after_delay():
        run = runs[reader["email"]]
        evidence.data(steps, "their run", run)
        waited = (datetime.fromisoformat(run["sent_at"]) -
                  datetime.fromisoformat(run["enrolled_at"])).total_seconds()
        assert waited >= DELAY_S, (f"sent {waited:.1f}s after the tag was added; "
                                   f"the delay is {DELAY_S}s")
        return f"sent {waited:.1f}s after the tag was added"
    steps.step("it was sent no earlier than its delay", after_delay,
               expected=f"at least {DELAY_S}s between the tag and the email, by the app's clock",
               found=str)

    def held_back():
        # Both runs are finished, so anything sent to them is already in the inbox.
        leaked = inbox.search(subject=subject, to=gone["email"])
        for message in leaked:
            evidence.email(steps, inbox, message, "the email they received")
        assert not leaked, f"the unsubscribed contact {gone['email']} received the email"
    steps.soft_step("the unsubscribed contact got nothing", held_back,
                    expected="no copy for the unsubscribed address, while the other arrived",
                    means="An automation emailed someone who had unsubscribed.")

    def skipped():
        run = runs[gone["email"]]
        evidence.data(steps, "their run", run)
        assert (run["status"], run["reason"]) == ("skipped", "unsubscribed"), (
            f"their run is {run['status']!r} ({run['reason']})")
    steps.soft_step("the app shows their run skipped as unsubscribed", skipped,
                    expected="status skipped, reason unsubscribed")
    steps.raise_soft_failures()
