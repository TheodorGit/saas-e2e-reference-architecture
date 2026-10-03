# Case studies

Nine kinds of defect that end-to-end suites of SaaS products often miss: the symptom,
why a simple test misses it, and the pattern that catches it. Each one is a defect
switch in the example app, and the named test fails when it is switched on
(`example/suite/bug_matrix.py`).

## 1. A rule the app must enforce is ignored

**Symptom.** The app skips one of its rules and still reports success. In the example, a
send reaches someone on an address suppression list.
**Why a simple test misses it.** It checks that the action succeeded, or that a count
looks right. A count does not show who is missing or extra, and seeing nothing happen to
the excluded case means nothing if the action never ran.
**The pattern.** Include the case the rule exists for, so only the rule keeps it out,
and add a positive control: an ordinary case that must go through. Here, the excluded
address is in the audience, each recipient's own copy is collected, and every
audience member must be either delivered or excluded, not both (patterns 9, 13).
**In the example.** `suppression_leak` -> `test_email_batch_send_with_suppression`.

## 2. One action is billed twice

**Symptom.** A paid action appears twice in the billing journal.
**Why a simple test misses it.** It checks the on-screen confirmation, which is
correct. The journal is written later, so a check right after the action sees nothing.
**The pattern.** Record what each action should cost in a ledger when it succeeds.
At the end, poll for the journal to catch up, then check one row per action, the exact
amount, and no other rows (patterns 1, 2, 13).
**In the example.** `double_billing` -> `test_billing_journal_reconciles`.

## 3. A report is one recipient short

**Symptom.** A delivery or engagement report undercounts.
**Why a simple test misses it.** It checks "at least one", or allows a tolerance
because numbers on a shared account are never exact. The tolerance hides the defect.
**The pattern.** The run makes the opens and clicks itself and records who it engaged.
Compare the report's lists with those sets, and each count with its list. A known
undercount can be allowed for its measured amount, shown as amber (patterns 10, 12, 13).
**In the example.** `report_undercount` -> `test_report_cards_list_and_api_agree`.

## 4. The delivered email differs from the one written

**Symptom.** A raw template variable (`{{first_name}}`) reaches the reader, or a
required header, such as the one for one-click unsubscribe, is missing.
**Why a simple test misses it.** It checks that a message arrived and stops. Checking
only for leftover variables also misses a variable that rendered as nothing.
**The pattern.** Write the content standard as code and check every delivered message
against it: no leftover variables, the expected values present, the unsubscribe link
and header line present, and the RFC 8058 headers correct (pattern 11).
**In the example.** `literal_template_variable` and `missing_one_click_post` ->
`test_content_standard`.

## 5. The page shows its guess, not the server's answer

**Symptom.** After a bulk action the list shows the change, but only as the page's
optimistic update; the real state never replaces it.
**Why a simple test misses it.** It clicks, sees the change and passes, whether or not
the server agreed.
**The pattern.** The action ends when no optimistic item is left, and the state is then
checked through the API (pattern 20).
**In the example.** `no_list_refresh` -> `test_bulk_tag_live_refresh`.

## 6. A confirmation that is not true

**Symptom.** The page says saved, resubscribed or deleted, but nothing changed.
**Why a simple test misses it.** It checks the confirmation message, which the defect
still shows.
**The pattern.** After the page confirms, read the state back through the API, and
record the change in the ledger only once the API agrees (patterns 2, 12).
**In the example.** `resubscribe_ignored` -> `test_unsubscribe_and_resubscribe`;
`delete_not_persisted` -> `test_ui_delete`.

## 7. Unsubscribing counts as engagement

**Symptom.** Unsubscribing registers as a click.
**Why a simple test misses it.** Unsubscribe tests check the status; engagement tests
check that clicks are at least what the run caused. Neither notices extra clicks.
**The pattern.** Engagement the run owns, compared exactly, and explicit expectations
for side effects: an unsubscribe counted as a click is False; whether a one-click
unsubscribe counts as an open is product policy, so it is recorded, not asserted. A
marker open fired after the unsubscribes shows when their effects have landed
(patterns 10, 15).
**In the example.** `unsubscribe_counts_click` -> `test_unsubscribe_is_not_engagement`.

## 8. A rule with a rolling window

**Symptom.** "Repeating this within N seconds is free", but the repeat is billed, or
the free period never ends.
**Why a simple test misses it.** It assumes the second one is free. When the run is
slow, it fails as if the product were broken, and gets loosened until it cannot fail.
**The pattern.** Decide per action, from the run's own clock, whether it is inside the
window, outside it, or too close to the edge to call; in the last case, record what was
charged. Cross the window by waiting, and confirm the clock really passed the edge
(patterns 14, 15).
**In the example.** `free_window_ignored` -> `test_validate_single_address`.

## 9. An automation emails someone who unsubscribed

**Symptom.** An automation (a tag is added, a delay runs out, an email goes out) sends
to a contact who unsubscribed, often during the delay.
**Why a simple test misses it.** It enrolls one subscribed contact, sees the email and
passes. Nobody enrolls a contact who should be skipped.
**The pattern.** Enroll an unsubscribed contact and a subscribed positive control in the
same automation. When both runs finish, check that the control's copy arrived, no
earlier than the delay, and that the unsubscribed contact got nothing (patterns 9, 13,
20).
**In the example.** `automation_ignores_unsubscribe` -> `test_automation_skips_unsubscribed`.

## A defect in the suite itself

The bug matrix also catches defects in the tests. While the example was built, a
verification test re-read the dashboard by navigating to the address it was already on.
The page did not re-render, so the test compared stale numbers until its time ran out.
It failed on a clean run, and because it was neither a guard nor a declared impact, the
matrix check reported it as a separate defect.
