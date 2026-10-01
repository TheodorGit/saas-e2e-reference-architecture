# Case studies

Nine defect classes that end-to-end suites of SaaS products commonly let through.
Each is described generically: the symptom, why a naive test misses it, and the
pattern that catches it. Each is also a switch in the example app, so the catch is
not a claim: the named test goes red when the defect is switched on
(`example/suite/bug_matrix.py`).

## 1. An excluded recipient still gets the email

**Symptom.** A send honours its audience but not its exclusions: someone on an
address suppression list receives it.
**Why naive testing misses it.** The test checks that the send "succeeded", or that
the count of recipients looks plausible. A count cannot tell a missing recipient
from an extra one, and an empty inbox for the excluded address proves nothing if the
send never happened at all.
**The pattern.** Put the excluded address IN the audience, so only the exclusion can
keep it out, and add a positive control - an ordinary recipient whose copy must
arrive. Collect each recipient's own copy. Then assert a partition: every audience
member is delivered or excluded, never both, never neither (patterns 9, 13).
**In the example.** `suppression_leak` -> `test_email_batch_send_with_suppression`.

## 2. One action is billed twice

**Symptom.** A paid action appears twice in the billing journal; the balance drops
twice.
**Why naive testing misses it.** The test reads the confirmation on screen ("charged
5 credits"), which is right. The journal is written asynchronously, after the test
has moved on, and a check that runs right after the action sees nothing yet - so it
either races or is skipped.
**The pattern.** Record what each action should cost, in a ledger, the moment it
succeeds. Reconcile once, at the end, after polling for the journal to catch up:
exactly one row per recorded action, the exact amount, and no unexplained rows
(patterns 1, 2, 13).
**In the example.** `double_billing` -> `test_billing_journal_reconciles`.

## 3. A report quietly drops a recipient

**Symptom.** A delivery or engagement report is one short.
**Why naive testing misses it.** The test asserts "at least one", or allows a
tolerance because the numbers on a shared account are never exact. A tolerance that
absorbs noise also absorbs the defect.
**The pattern.** Make the numbers exact by owning them: the run fires the opens and
clicks itself and records WHO it engaged. Compare the report's lists with those
sets, and each count with its own list's length. A known shortfall can be granted as
amber, measured per entry, never as a blanket tolerance (patterns 10, 12, 13).
**In the example.** `report_undercount` -> `test_report_cards_list_and_api_agree`.

## 4. The email that arrives is not the email that was written

**Symptom.** A raw template variable (`{{first_name}}`, often called a merge tag)
reaches the reader, or a required header - such as the one that enables one-click
unsubscribe - is missing.
**Why naive testing misses it.** The test proves delivery ("a message with this
subject arrived") and stops. Nobody reads the headers, and checking only for leftover
variables misses a variable that rendered to nothing.
**The pattern.** Encode the content standard as code and assert every delivered
message against it: no literal variable, the expected values present, the unsubscribe
link and header line present, the RFC 8058 headers exactly right (pattern 11).
**In the example.** `literal_template_variable` and `missing_one_click_post` ->
`test_content_standard`.

## 5. The screen shows its own guess, not the server's answer

**Symptom.** After a bulk action the list shows the change, but it is the page's
optimistic guess; the real state (or a failure) never replaces it.
**Why naive testing misses it.** The test clicks, sees the change appear, and passes -
on the optimistic render, which appears whether or not the server agreed.
**The pattern.** An action ends on the server's answer, not the first visible change:
wait until no optimistic item is left, then confirm the same state through the API
(pattern 20).
**In the example.** `no_list_refresh` -> `test_bulk_tag_live_refresh`.

## 6. A confirmation that is not true

**Symptom.** The page says "done" - saved, resubscribed, deleted - but the system
never made the change.
**Why naive testing misses it.** The test asserts the confirmation message, which is
exactly what the defect gets right.
**The pattern.** Prove every action on a surface independent of the one that drove
it: after the page confirms, read the state back through the API. Record the change
in the ledger only once that surface agrees, so downstream checks never believe the
page either (patterns 2, 12).
**In the example.** `resubscribe_ignored` -> `test_unsubscribe_and_resubscribe`;
`delete_not_persisted` -> `test_ui_delete`.

## 7. Unsubscribing is counted as engagement

**Symptom.** Unsubscribing registers as a click, inflating engagement numbers.
**Why naive testing misses it.** Unsubscribe tests check that the address was
unsubscribed. Engagement tests check that clicks are at least what the run caused.
Neither looks at what an unsubscribe does to the stats, and "at least" hides a surplus.
**The pattern.** Engagement the run owns, with exact sets, and explicit expectations
for side effects: an unsubscribe counted as a click is False; whether a one-click
unsubscribe counts as an open is product policy, so it is observed and recorded, not
asserted.
Ingestion order is proven with a marker the run fires after the unsubscribes (patterns
10, 15).
**In the example.** `unsubscribe_counts_click` -> `test_unsubscribe_is_not_engagement`.

## 8. A rule on a rolling window

**Symptom.** "Repeating this within N seconds is free" - and the repeat is billed, or
the free period never ends.
**Why naive testing misses it.** The test hardcodes "the second one is free". It
passes until the run is slow, then fails like a product defect - so it gets
loosened, and then it cannot fail at all.
**The pattern.** Decide the expectation per action from the run's own clock: inside
the window, outside it, or too close to the edge to call - and then observe and
record. Cross the window by the clock, confirming the wall clock really passed the
edge (patterns 14, 15).
**In the example.** `free_window_ignored` -> `test_validate_single_address`.

## 9. An automation emails someone who unsubscribed

**Symptom.** An automation - a tag is added, a delay runs out, an email goes out -
sends to a contact who unsubscribed, often during the delay itself.
**Why naive testing misses it.** The test adds the tag to one subscribed contact, sees
the email arrive, and passes. Nobody enrolls a contact who should be held back, and
an empty inbox proves nothing if the automation never ran at all.
**The pattern.** Enroll two contacts in the same automation: one unsubscribed, and a
subscribed positive control. Wait for both runs to finish, read through the API, then
assert the control's own copy arrived - no earlier than its delay - and the
unsubscribed contact got nothing (patterns 9, 13, 20).
**In the example.** `automation_ignores_unsubscribe` -> `test_automation_skips_unsubscribed`.
One automation is covered; the same pattern extends to multi-step sequences, goals and
exit conditions.

## A note on the suite's own defects

The same discipline catches defects in the tests. While this example was built, a
verification test re-read a single-page dashboard by navigating to the address it was
already on; the view never re-rendered, and the test compared stale numbers for its
whole polling budget. It went red on a clean run - and, because every red test must
be either a flag's guard or a declared impact, the matrix check labelled it a
separate defect instead of letting it hide among expected failures.
