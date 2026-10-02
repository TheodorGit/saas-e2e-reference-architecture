# Architecture

Two parts: [the patterns](#part-1-the-patterns), each with the problem it solves and
where it lives, and [applying them to your product](#part-2-applying-it-to-your-product),
step by step, as `example/` does.

```
framework/   product-agnostic core: pipeline, reporting, delivery, safety, api, ui
example/
  app/       the Demo ESP App, a fictional email service provider (FastAPI + a no-build SPA)
  suite/     page objects, components and tests for the Demo ESP App, built on framework/
scripts/     the identifier denylist check, the bug-matrix checker, the sample-report site builder
docs/        the patterns, how to run it, case studies
```

`framework/` never imports `example/` and names no product feature; a unit test checks
both.

# Part 1: the patterns

## Pipeline

### 1. Staged run: baseline, actions, verification
**Problem.** Billing journals, reports and dashboards update late. Checking each action
right after it runs is racy, and absolute values mean nothing on a shared account.
**Pattern.** Three stages. Baseline reads the system before the run changes it; actions
act and record what they did; verification compares everything once, at the end, as
exact changes from the baseline. The order is set by path (`e2e_stages` ini option),
because pytest regroups tests that share parametrized fixtures and would otherwise run
browser-less tests after verification.
**Where.** `framework/pipeline/stages.py`, used by `framework/pytest_plugin.py`.

### 2. Session ledger and exact reconciliation
**Problem.** Numbers a test cannot account for rule out exact checks, and tolerances
hide defects.
**Pattern.** Each action records what it cost, aimed at and sent, as soon as it
succeeds. Verification compares the ledger with the system. The ledger is saved on
every write and uses UTC. Totals come from one function (`totals.tally`) used by both
the report and the checks.
**Where.** `framework/pipeline/ledger.py`, `framework/pipeline/totals.py`, fixture
`e2e_ledger`.

### 3. The run manifest lists the tests
**Problem.** A report built from step files leaves out a test that failed in a fixture,
because it never wrote one.
**Pattern.** Every phase of every test is recorded in a manifest, rewritten after each
phase. A test that was still running when the process died is reported as interrupted.
The report takes its list of tests from the manifest.
**Where.** `framework/pipeline/manifest.py`.

### 4. Replay
**Problem.** Verification that waits for slow ingestion can take an hour to reach, and
re-running the actions each time is expensive.
**Pattern.** Run verification against an earlier run's ledger. Entries and baselines are
reused; created entities are not, so cleanup never touches another run's data. The
pytest header says when a run is a replay.
**Where.** `framework/pipeline/replay.py`, `Ledger.replay`, `E2E_REPLAY_LEDGER`.

## Reporting

### 5. Steps that declare what they expect
**Problem.** A bare assert fails with an error line and nothing else.
**Pattern.** A step states its expectation before it runs. On failure the report shows
EXPECTED (the stated expectation), INSTEAD (the exception's first line) and MEANS (a
sentence written by the test, or one derived from the exception type, or nothing).
**Where.** `framework/reporting/recorder.py`, `failure_reasons.py`, fixture `steps`.

### 6. Soft steps and checks that did not run
**Problem.** One failed check stops the test and hides the checks after it, and a check
that never ran looks like one that passed.
**Pattern.** `soft_step` records a failure and continues; the test fails once at the
end, listing all of them. If the test does not raise them, the `steps` fixture does in
teardown (pattern 18). `skip_step` records a check that did not run, and why; it is
shown as not run and does not count as passed. `known_issue` records an accepted defect
as amber.
**Where.** `framework/reporting/recorder.py`.

### 7. A report for every run
**Problem.** A report that only arrives when a run passes is not useful.
**Pattern.** At the end of the session the builder writes `report.html`, `email.html`
and `summary.json`, and mails them over plain SMTP, not through the system under test.
Building or mailing the report never changes the run's result. Steps are matched to
tests by nodeid; steps for a test missing from the manifest are reported as a warning.
**Where.** `framework/reporting/report_builder.py`, `mailer.py`, `profiles.py`.

## Delivery

### 8. Unique tokens
**Problem.** Searching an inbox by a fixed subject finds earlier runs' mail.
**Pattern.** Every run has an id, and every subject and created entity carries a token
built from it. Searches and cleanup use the token.
**Where.** `framework/tokens.py`, fixtures `run_id`, `subject_token`, `entity_name`.

### 9. Delivery checked in an inbox
**Problem.** "The API returned 200" does not mean the email was delivered.
**Pattern.** A `MailClient` interface with five operations (search, html, headers, raw,
delete), with waiting and per-recipient collection built on top. Each recipient's own
copy is collected, so a missing recipient is named. `raw` is the message as delivered,
kept as evidence when an inbox check fails (pattern 17).
**Where.** `framework/delivery/mail_client.py`; the Mailpit adapter `mailpit.py`, tested
against a real Mailpit by `framework/tests/test_mailpit_live.py` (in CI).

### 10. Engagement the run creates itself
**Problem.** Open and click counts include engagement the run did not cause, so they
cannot be checked exactly.
**Pattern.** The run fetches the tracking pixel and tracked links itself and records
which addresses it engaged. Counts are the lengths of those lists. A failed fetch is
reported as a failure, not counted.
**Where.** `framework/delivery/links.py` (`engage`).

### 11. The content standard as code
**Problem.** "The email looks right" is not a check.
**Pattern.** No literal template variable (`{{first_name}}`) may reach the inbox, and
the expected values must be present, which also catches a variable that rendered as
nothing. The unsubscribe footer link and header line are required, and so are the
RFC 8058 one-click headers. `one_click_url(..., allowed_schemes=)` accepts https only by
default, as RFC 8058 requires; a local stack served over http passes http explicitly.
**Where.** `framework/delivery/content_checks.py`, `one_click.py`.

## Verification

### 12. Checking each surface separately, and amber for known undercounts
**Problem.** Two surfaces fed by the same pipeline can agree while both are wrong, and a
known undercount fails every run until it is fixed.
**Pattern.** Compare the run's own record with each surface separately, including work
from actions that failed, so a defect shows everywhere it reaches. A known undercount
is measured per entry (`totals.shortfall`) and allowed for exactly that amount, shown as
amber; when the defect is fixed the allowance drops to zero without a test change. An
overcount is never allowed.
**Where.** `framework/pipeline/totals.py`. In the example, the journal, the dashboard
and the report each have their own verification test
(`example/suite/tests/verification/`).

### 13. Set differences and partitions
**Problem.** A matching count can hide a missing recipient and an unexpected one.
**Pattern.** Compare sets and report both differences: who is missing and who is
unexpected. Where outcomes are exclusive, check that each audience member is in exactly
one outcome and that no outcome holds an outsider. An empty expected set fails unless
the call passes `allow_empty=True`. A check with nothing to check in a run is recorded
as not run.
**Where.** `framework/pipeline/sets.py`. In the example: report lists against the run's
recipients and engagement, the audience split into delivered and suppressed, journal
references against billed actions, the export against the filtered list, an email
batch's audience against the contacts the test created, and an automation's enrolled
contacts against the ones the tag was added to.

### 14. Rolling windows
**Problem.** With a rule like "repeating this within N seconds is free", the expected
cost depends on timing. Assuming the second one is free fails whenever the run is slow.
**Pattern.** Decide per action, from the run's own record of when the window opened,
whether it is inside, outside, or too close to the edge to call. When too close, record
the cost actually shown (pattern 15), so the final reconciliation still balances. The
window is crossed by waiting a stated, bounded time.
**Where.** `framework/pipeline/windows.py`. In the example:
`example/suite/tests/actions/test_validation.py`. On Docker Desktop the VM's clock has
been measured stepping back 1.5 s during a sleep, which is why there is a margin.

### 15. Expectations that are True, False, or observed
**Problem.** Some behaviour has a required answer; some is product policy the test
should not decide.
**Pattern.** Each expectation is True, False or OBSERVE. OBSERVE records the value in
the report without asserting it, and can later be changed to True or False.
**Where.** `framework/pipeline/expectations.py`. In the example,
`example/suite/tests/verification/test_unsubscribe_engagement.py`: an unsubscribe
counted as a click is False; a one-click unsubscribe counted as an open is OBSERVE.

## Safety and evidence

### 16. Guards before anything is sent
**Problem.** A suite that acts on a live system could email real people or change data
it does not own.
**Pattern.** The run stops before acting when an audience is above its cap, when a
member is neither the run's own nor declared by name, or when a destructive test runs
without `E2E_ALLOW_DESTRUCTIVE=1` (the plugin skips it).
**Where.** `framework/safety/guards.py`, destructive-test gating in the plugin.

### 17. Keep a failure's evidence, clean up only what passed
**Problem.** Deleting a failed test's data deletes the evidence.
**Pattern.** Created entities are registered in the ledger. When a test fails,
everything that exists at that moment is kept; entities created later are cleaned up as
usual. A failed test keeps one folder holding what each failed check saw: an inbox check
keeps the email (`.html`, `.eml`, headers), an API check the request and response, a
reconciliation the rows it read, and a screen check (`ui=True`) its screen and the
test's trace. Files are numbered by check and named for what they are
(`06 the email they received.html`, `04 screen.png`); the folder's `test.txt` lists every
check with its number and result. The report links each check to its files. A passing
test keeps no evidence. Every browser test also keeps a video, and the example's runner
shows the browser live unless it runs headless.
**Where.** `Ledger.preserve_all` (called by the plugin on any failure),
`StepRecorder.attach` and `framework/reporting/evidence.py`, `framework/ui/tracing.py`
(screens, traces and videos), `example/suite/entrypoint.sh` (the live view).

## API

### 18. A test cannot pass while holding a failed step
**Problem.** API tests make many independent checks, so they record failures and
continue. A test that forgets to raise them at the end, or returns early, passes with a
failure in it.
**Pattern.** Every call is a step that states the expected method, route and status
and records the answer; checks on the body are steps too. The `steps` fixture raises
any recorded failure in teardown, for API and UI tests alike. A request that could not
be sent is a failed step.
**Where.** `framework/api/recorder.py`, fixtures `api_recorder` and `steps`.
`framework/tests/test_api.py` shows the difference: without the teardown raise, a toy
run reports "[PASSED] all 2 tests passed - 1 of 2 checks passed"; with it, those tests
fail. In the example: `example/suite/tests/api/`.

### 19. Docs coverage
**Problem.** A documented endpoint that no test calls goes untested, usually when it is
new.
**Pattern.** Each recorded call is counted by its route template, not the concrete URL.
At the end of the session the documented endpoints (from the product's own index) are
compared with the called ones, both ways. Only this session's calls count, so running a
subset of tests checks a subset and says so.
**Where.** `framework/api/coverage.py`, fixture `api_coverage`. In the example,
`example/suite/tests/verification/test_api_docs.py` checks against the app's `/v1/`
index. The smoke test reads the same index, so a new read with no parameters is covered
automatically; one with parameters needs its own test.

## UI

### 20. Page objects, roleless widgets, and actions that end on their result
**Problem.** Single-page apps finish things late: a confirmation shows before the
request finishes, a number paints after its label, a list shows an optimistic update
and re-reads later, a badge changes its text in place, a search waits for typing to
pause. A test that moves on at the first visible change reads the wrong state.
**Pattern.** One page object per page; every action ends on its own result:
- a form ends on the new row, not on the "saved" toast;
- a number is read once it is a number, not the placeholder;
- a bulk action ends when no pending item is left;
- a debounced search waits for the request with this query, then for the table;
- a status is awaited by its text on the element.
Locators use role, label, text and test id. A widget with no roles (a custom dropdown)
gets a component that uses CSS only inside its test-id container. Icon words end up in
accessible names ("delete Delete"), so names are matched by their label with an
optional icon word in front.
**Where.** `framework/polling.py`, `framework/ui/names.py` (`label_pattern`). In the
example: `example/suite/pages/` and `example/suite/components/` (`RolelessDropdown`,
`ConfirmDialog`, `painted_number`).

# Part 2: applying it to your product

These are the steps `example/` takes to apply `framework/` to the Demo ESP App, in
order, each with where the example does it. None of them changes `framework/`; if you
need to, add a documented extension point instead, as `one_click_url(allowed_schemes=)`
was added for a local http stack.

### Step 1. Enable the plugin and declare the stages

In the suite's top-level `conftest.py`:

```python
pytest_plugins = ["framework.pytest_plugin"]

def pytest_configure(config):
    for line in ("my_suite/tests/baseline/ = 0", "my_suite/tests/actions/ = 1",
                 "my_suite/tests/verification/ = 2"):
        config.addinivalue_line("e2e_stages", line)
```

Setting `e2e_stages` here keeps the option out of runs that do not load the plugin.
**Example:** `example/suite/conftest.py`.

### Step 2. Configuration from the environment

One frozen config object read from environment variables, with defaults that point at
a local stack and need no secrets. Include the safety limits (the audience cap) and the
waiting budgets. Test recipients are plus-aliases of one inbox.
**Example:** `example/suite/config.py`.

### Step 3. Clients for the other surfaces

Thin clients for every surface besides the UI; here, the signed-in app API and the
public API. Verification reads through them.
**Example:** `example/suite/app_client.py`.

### Step 4. Define your ledger entries

Name the entry kinds your actions record, and give each total one counter function,
used by both the report and the checks (`totals.tally`).
**Example:** `example/suite/ledger_kinds.py`.

### Step 5. Register a report profile

Test titles, sections in reading order, and a summary of what the run did, computed
from the ledger.
**Example:** `example/suite/profile.py`.

### Step 6. Describe your email

Pick a `MailClient` (the example uses the Mailpit adapter) and describe your product's
tracker URLs (`TrackerPatterns`) and unsubscribe standard (`UnsubscribeStandard`).
**Example:** `TRACKERS` and `UNSUBSCRIBE` in `example/suite/app_client.py`; the `inbox`
fixture in `example/suite/conftest.py`.

### Step 7. Fixtures

- A session fixture that fails clearly when the product is unreachable.
- Browser contexts built by hand (to reuse a session) get
  `framework.ui.tracing.Evidence`: every browser test keeps a video, and the trace and
  screens are kept when a UI check fails.
- A `record` fixture that adds the test's name to each ledger entry.
- Factories that create the run's entities and `register_entity` them.
- A session cleanup that removes `cleanup_targets()` only; a failure's entities are kept
  by the plugin.
- `v1`-style fixtures built with `api_recorder` for the public API.

**Example:** `example/suite/conftest.py`.

### Step 8. Baseline

Before anything acts, read every surface verification will compare against and
`snapshot` it into the ledger. Each step says what it found (`found=`), e.g. "Newest row
is #413".
**Example:** `example/suite/tests/baseline/test_baseline.py`.

### Step 9. Actions

Each action test acts through the UI or API, ends every UI action on its result, and
records what it did once a different surface confirms it. The safety guards
(`assert_within_cap`, `assert_owned`) run before anything is sent.

Mark every check of what is on screen `ui=True`. Inside other checks, `attach` what the
check read before asserting: the email for an inbox check, the rows or response for the
rest. It is kept only if that check fails.
**Example:** `example/suite/tests/actions/`, `example/suite/evidence.py`.

### Step 10. Page objects and components

One page object per page; actions end on their result. Widgets without roles get a
component. Buttons with icon words are matched with `label_pattern`.
**Example:** `example/suite/pages/`, `example/suite/components/`.

### Step 11. Verification

Poll each slow surface for the real condition within a budget (`poll_until`), then
compare it exactly with the ledger: sets rather than counts (`framework.pipeline.sets`),
rolling windows decided per action (`framework.pipeline.windows`), and policy observed
rather than asserted (`framework.pipeline.expectations`). Each comparison attaches the
rows it read as evidence.
**Example:** `example/suite/tests/verification/`.

### Step 12. API tests and docs coverage

Call the public API through `api_recorder`. A smoke test walks the product's own
endpoint index, full tests cover what needs data, and the session ends with the
docs-coverage check against the same index.
**Example:** `example/suite/tests/api/`, `example/suite/tests/verification/test_api_docs.py`.

### Step 13. Show that every test can fail

For each test, a switch in the product that injects the defect it guards, and a bug
matrix naming the test, the check that must fail, and any other test the defect is
known to affect, with the reason. A checker compares each run with the matrix and
reports any other failure as a separate defect. CI runs the clean product (must pass)
and every switch (each must fail at its guard).
**Example:** `example/app/bugs.py`, `example/suite/bug_matrix.py`,
`scripts/check_flag_run.py`, `.github/workflows/ci.yml`.

### Step 14. One command

A compose file that starts the product, its dependencies, an inbox and the test runner,
and returns pytest's exit code (`--exit-code-from tests`). The report is mailed to the
inbox and written to disk, and `reports/latest.html` opens the newest one.
**Example:** `docker-compose.yml`, `example/suite/Dockerfile`.
