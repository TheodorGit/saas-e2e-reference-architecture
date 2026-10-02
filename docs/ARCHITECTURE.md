# Architecture

Two parts: [the patterns](#part-1-the-patterns), each with the problem it solves and
where it lives, and [applying it to your product](#part-2-applying-it-to-your-product),
step by step, the way `example/` does it.

```
framework/   product-agnostic core: pipeline, reporting, delivery, safety, api, ui
example/
  app/       the Demo ESP App, a fictional email service provider (FastAPI + a no-build SPA)
  suite/     page objects, components and tests for the Demo ESP App, built on framework/
scripts/     the identifier denylist check run on every commit, the bug-matrix checker,
             and the sample-report site builder
docs/        the patterns and how to adopt them, how to run it, case studies
```

`framework/` never imports `example/` and names no product feature; a unit test enforces
both.

# Part 1: the patterns

Each pattern: the problem, the pattern, and where it lives.

## Pipeline

### 1. Staged run: baseline, actions, verification
**Problem.** Verifying a SaaS product means asserting on surfaces that update late:
billing journals, reports, dashboards. Checking each action right after it runs is
racy, and checking absolute values is meaningless on a shared account.
**Pattern.** Three stages. Baseline reads the system before the run touches it;
actions act and record what they did; verification reconciles everything once, at the
end, as exact deltas from the baseline. Order is imposed by path with a stable sort
(`e2e_stages` ini option), because pytest regroups tests that share parametrized
fixtures and would otherwise move browser-less tests after verification.
**Where.** `framework/pipeline/stages.py`, wired in `framework/pytest_plugin.py`.

### 2. Session ledger and exact reconciliation
**Problem.** Numbers a test cannot account for make exact assertions impossible, and
tolerances hide real defects.
**Pattern.** Every action records, the moment it succeeds, what it cost, what it
aimed at and what it sent, keyed by the run's token. Verification reconciles the
ledger against the system. The ledger is saved on every write (a crashed run keeps
its record) and uses UTC throughout. Derived numbers (`totals.tally`) come from one
function read by both the report and the checks, so they cannot disagree.
**Where.** `framework/pipeline/ledger.py`, `framework/pipeline/totals.py`,
fixture `e2e_ledger`.

### 3. The run manifest is the authority
**Problem.** A report built from step files silently drops a test that died in a
fixture, because it never wrote one.
**Pattern.** Every phase of every test is folded into a manifest that is rewritten
after each phase. A test still running when the process dies is reported as
interrupted, never as passed. The report treats the manifest as the list of tests.
**Where.** `framework/pipeline/manifest.py`.

### 4. Replay
**Problem.** Verification that waits on slow ingestion can take an hour to reach;
iterating on it by re-running the actions is expensive.
**Pattern.** Point verification at an earlier run's ledger. Entries and baselines are
carried; entities are not, so cleanup never touches another run's work. Replay is
announced in the pytest header so a green replay cannot pass for a real run.
**Where.** `framework/pipeline/replay.py`, `Ledger.replay`, `E2E_REPLAY_LEDGER`.

## Reporting

### 5. Steps that declare what they expect
**Problem.** A bare assert fails with an error line and nothing else: the reader
cannot tell what was supposed to happen.
**Pattern.** A step declares its expectation before it runs. On failure the report
shows EXPECTED (declared), INSTEAD (the real exception's first line) and MEANS (an
authored product-level statement, else a factual sentence classified from the
exception type, else nothing - never a guess).
**Where.** `framework/reporting/recorder.py`, `failure_reasons.py`, fixture `steps`.

### 6. Soft steps and checks that did not run
**Problem.** One failed check aborts the test and hides the state of every
independent check after it; a check that never ran looks like one that passed.
**Pattern.** `soft_step` records and continues, and the test fails once at the end
with all of them - raised by the test, or else by the `steps` fixture's teardown, so
a test can never pass while holding a failed step (pattern 18). `skip_step` records a check that did not run, and why: it counts as
a hole in coverage in the report and the email, never toward the pass count.
`known_issue` records an accepted defect as amber - visible, never green.
**Where.** `framework/reporting/recorder.py`.

### 7. Reports on every run
**Problem.** A report that only arrives when things go well is not a report.
**Pattern.** At session end the builder writes `report.html` (full detail; failures
open, passes collapsed), `email.html` (failures first, mail-client-safe markup) and
`summary.json`, and mails them over plain SMTP - never through the system under test.
Building or mailing never changes the run's outcome. Steps attach to tests by nodeid;
steps recorded for a test the manifest never saw are reported as an integrity warning.
**Where.** `framework/reporting/report_builder.py`, `mailer.py`, `profiles.py`.

## Delivery

### 8. Unique tokens
**Problem.** Searching an inbox by a fixed subject finds earlier runs' mail.
**Pattern.** Every run has an id; every subject and created entity carries a token
built from it. A search for the token can only find this run's work, and cleanup can
bin exactly this run's mail.
**Where.** `framework/tokens.py`, fixtures `run_id`, `subject_token`, `entity_name`.

### 9. Proving delivery in an inbox the run can read
**Problem.** "The API returned 200" is not delivery.
**Pattern.** A `MailClient` interface with five primitives (search, html, headers,
raw, delete); waiting and per-recipient collection are built once on top. Each
recipient's OWN copy is collected, so a missing recipient is named, not averaged away.
`raw` is the message exactly as delivered: what a failed inbox check keeps as
evidence (pattern 17).
**Where.** `framework/delivery/mail_client.py`; Mailpit adapter `mailpit.py`, proven
against a live Mailpit by `framework/tests/test_mailpit_live.py` (runs in CI).

### 10. Engagement the run owns, itemised by recipient
**Problem.** Open and click counts include engagement the run did not cause, so an
exact assertion on them is impossible - unless the run knows exactly what it caused.
**Pattern.** The run fetches the tracking pixel and tracked links itself, and records
WHICH addresses it engaged. Counts are the length of those lists, so a count and its
addresses cannot disagree, and a surplus can be traced to someone who is not the run.
A fetch that failed is reported as a failure, never counted.
**Where.** `framework/delivery/links.py` (`engage`).

### 11. Content checks as an encoded standard
**Problem.** "The email looks right" is not a check.
**Pattern.** The standard is code: no literal template variable (`{{first_name}}`, often
called a merge tag) may reach the inbox, and the expected values must be present (a
variable rendering to nothing leaves nothing to find); the unsubscribe footer link and
header line are required; RFC 8058 one-click headers are required. A mismatch is a
finding about the email, never a reason to relax the check.
The one extension point is `one_click_url(..., allowed_schemes=)`: https only by
default, as RFC 8058 requires; a local stack served over http widens it explicitly
instead of skipping the check.
**Where.** `framework/delivery/content_checks.py`, `one_click.py`.

## Verification

### 12. Proof on independent surfaces, and the amber/red rule
**Problem.** Two surfaces fed by the same pipeline agree with each other while both
are wrong; a known undercount turns every run red until it is fixed.
**Pattern.** Assert the run's own expectation against each surface separately. A
known undercount is measured per entry (`totals.shortfall`) and granted only for that
exact amount, as amber; it shrinks to zero the day the defect is fixed, with no test
change. An overcount is never an allowance.
Every surface is checked against the ledger, including work from an action that
failed: a defect shows everywhere it reaches, and the report shows its full impact.
**Where.** `framework/pipeline/totals.py`. In the example: the journal, the dashboard
and the report are each checked against the ledger in their own verification test
(`example/suite/tests/verification/`).

### 13. Set-difference and partition assertions
**Problem.** A count that matches can hide two errors that cancel: one expected
recipient missing, one stranger present. "2 delivered" is right while both are wrong.
**Pattern.** Compare SETS and name both sides of the difference: who is missing, who
is unexpected. Where outcomes are exclusive, assert a partition: every member of the
audience is in exactly one outcome (delivered or suppressed), never both, never
neither, and no outcome holds an outsider.
A check never passes on nothing: "nobody unexpected received it" is also true when
nobody was sent anything. So an empty expected set fails, unless the call says empty
is the point (`allow_empty=True`, as for "no row shows the removed tag"). Where there
is legitimately nothing to check in a run, the check is recorded as not run - visible
in the report and the email - never as a pass.
**Where.** `framework/pipeline/sets.py`. In the example: report lists vs the run's
recipients and engagement, the audience partition (delivered/suppressed), journal
references vs billed actions, the export vs the filtered list, the email batch's
audience vs exactly the contacts the test created, and the contacts an automation
enrolled vs exactly the ones the trigger tag was added to.

### 14. Rolling windows: keeping a delta exact while the window moves
**Problem.** Rules like "re-doing this within N seconds is free" make the expected
cost of an action depend on timing. Hardcoding "the second one is free" holds until
the run is slow, and then fails like a product defect.
**Pattern.** Decide the expectation per action, from the run's own record of when the
window opened: inside, outside, or - within a margin of the edge, where two clocks
cannot be trusted to the second - too close to call. Too close to call becomes an
observation (pattern 15), and the ledger records the cost actually shown, so the
later exact reconciliation still balances. Crossing the window is done by waiting on
the clock (nothing else can show it), with a bounded, stated wait.
**Where.** `framework/pipeline/windows.py`. In the example:
`example/suite/tests/actions/test_validation.py` (billed, free inside the window, billed
after it). On Docker Desktop the VM's wall clock has been measured stepping back by
1.5s during a sleep - exactly the case the margin exists for.

### 15. Three-valued expectations: true, false, observe-and-record
**Problem.** Some behaviours have a required answer; some are product policy the run
has no standing to assert. Forcing policy into true/false yields tests that break on
a policy change, or that assert whatever happened once.
**Pattern.** Each expectation is True, False, or OBSERVE. OBSERVE records the value in
the report ("observed, not asserted") without judging it; promoting it later is a
one-word change.
**Where.** `framework/pipeline/expectations.py`. In the example:
`example/suite/tests/verification/test_unsubscribe_engagement.py` - an unsubscribe
counted as a click is False; a one-click unsubscribe counted as an open is OBSERVE.

## Safety and evidence

### 16. Guards before anything is sent
**Problem.** A suite that acts on a live system can mail real people or change what
it does not own.
**Pattern.** Safety stops, stated as such: an audience above its cap, a member who is
neither ours nor declared by name, or a destructive test without an explicit opt-in
(`E2E_ALLOW_DESTRUCTIVE=1`; otherwise the plugin skips it) all refuse to proceed.
**Where.** `framework/safety/guards.py`, destructive gating in the plugin.

### 17. Keep a failure's evidence, clean up only what passed
**Problem.** Deleting a failed test's data destroys the evidence for the defect.
**Pattern.** Entities are registered in the ledger. When a test fails, everything that
exists at that moment is preserved - a failing check can only have read what was
created before it. Entities created afterwards are not its evidence and are cleaned up
normally. A failed test keeps one evidence folder, named after it, holding what each
failed check saw - of the kind that check was about: an inbox check keeps the email
(`.html`, `.eml`, headers), an API check the request and response, a reconciliation
the rows or report it read, and a screen check (`ui=True`) its screen, with the trace
of the test. Files are numbered by the check they belong to and named for what they
are: `06 the email they received.html`, `04 screen.png`. The check itself never goes
into a file name; the folder's `test.txt` lists every check with its number and
result, so a name stays short - and a downloaded report unpacks on Windows - however
long the check's sentence. A run token in a name is cut to its slug: the run's folder
already says which run. The report links each check to its own evidence. A passing
test keeps no evidence; collecting it never changes an outcome.
Separately, every browser test keeps a video, pass or fail, linked from the test in
the report - so a person can watch what the run did - and the example's runner shows
the browser live (headed on a virtual screen, viewable in a browser) unless told to
run headless.
**Where.** `Ledger.preserve_all` (called by the plugin on any failure),
`StepRecorder.attach` and `framework/reporting/evidence.py` (written by the plugin),
`framework/ui/tracing.py` (screens, trace and videos),
`example/suite/entrypoint.sh` (the live view).

## API

### 18. The recorder that cannot pass while holding a failed step
**Problem.** API tests make many independent checks, so they are written soft: one
wrong answer must not hide the rest. But soft checks must be raised at the end, and a
test that forgets - or returns early - passes while holding a failure. The report
then says PASSED over a failed step.
**Pattern.** Every call is a step that declares its expectation (method, route,
status) and records the answer; checks on the body are steps too, all soft. Raising
is not left to the test: the `steps` fixture raises every held failure in teardown,
so a test whose body passed still fails - API tests and UI tests alike. A request
that could not be made is a failed step, never coverage.
**Where.** `framework/api/recorder.py`, fixtures `api_recorder` and `steps` in the
plugin. Proven by `framework/tests/test_api.py` (with the teardown raise removed, a
toy run reports "[PASSED] all 2 tests passed - 1 of 2 checks passed"; with it, those
tests are failed). In the example: `example/suite/tests/api/`.

### 19. Docs coverage: a documented endpoint with no test reds the build
**Problem.** Documentation is a promise. An endpoint in it that no test calls is an
untested promise, and it rots silently - usually when it is new.
**Pattern.** Every recorded call is counted against its route TEMPLATE, not the
concrete URL. At the end of the session the documented endpoints (from the
product's own index) are compared with the executed ones, both ways: documented but
never executed, and executed but not documented. "This session" is literal: a run of
a subset of tests checks a subset, and says so, instead of trusting an earlier run.
**Where.** `framework/api/coverage.py`, fixture `api_coverage`. In the example:
`example/suite/tests/verification/test_api_docs.py` against the Demo ESP App's `/v1/` index;
the smoke test is driven by the same index, so a new parameter-less read is covered
by construction and a new parameterised one needs a written test.

## UI

### 20. Page objects, roleless widgets, and actions that end on their visible result
**Problem.** Single-page apps finish things late and out of sight: a confirmation
renders before its request finishes, a number paints after its label, a list shows
an optimistic guess and re-reads later, a badge changes its text while the element
stays, search waits for typing to pause. A test that moves on at the first visible
change reads a guess, and one that sleeps is slow and still wrong.
**Pattern.** One page object per page; every action ends on its own visible RESULT,
not on the first thing that appears:
- a form ends on the new row, not on the "saved" toast;
- a number is read once it is a number, not while it is the placeholder;
- a bulk action ends when no optimistic (pending) item is left - the server's answer;
- a debounced search waits for the request carrying THIS query, then for the table;
- a status is awaited by its text on the element that stays.
Locators go by role, label, text and test id. A widget with no roles (a custom
dropdown) gets a component that says so and uses CSS only inside its test-id root.
Icon ligatures pollute accessible names ("delete Delete"), so names are matched by
their label with an optional icon word in front - never by substring.
**Where.** `framework/polling.py` (the primitive), `framework/ui/names.py`
(`label_pattern`). In the example: `example/suite/pages/` and
`example/suite/components/` (`RolelessDropdown`, `ConfirmDialog`, `painted_number`).

# Part 2: applying it to your product

These are the steps, in order, that `example/` takes to apply `framework/` to the
Demo ESP App. Every step names where the example does it; do the same for your product.
Nothing here requires changing `framework/` - if you find you must reach inside it,
add a documented extension point instead (the way `one_click_url(allowed_schemes=)`
was added for a local http stack).

### Step 1. Enable the plugin and declare the stages

In the suite's top-level `conftest.py`:

```python
pytest_plugins = ["framework.pytest_plugin"]

def pytest_configure(config):
    for line in ("my_suite/tests/baseline/ = 0", "my_suite/tests/actions/ = 1",
                 "my_suite/tests/verification/ = 2"):
        config.addinivalue_line("e2e_stages", line)
```

Setting `e2e_stages` there keeps the option out of runs that do not load the plugin.
**Example:** `example/suite/conftest.py`.

### Step 2. Configuration from the environment, with safe defaults

One frozen config object, read from environment variables, with defaults that point
at a local stack and need no secrets. Include the safety limits (audience cap) and
the waiting budgets. Test recipients are plus-aliases of one inbox, and "ours" means
that inbox plus this run's id.
**Example:** `example/suite/config.py`.

### Step 3. Clients for the surfaces you will verify on

Write thin clients for every surface other than the UI: here the signed-in app API
and the public API. Verification reads through them to prove what the UI did.
**Example:** `example/suite/app_client.py`.

### Step 4. Say what your ledger entries mean

Name the entry kinds your actions record, and give each total ONE counter function,
read by the report's facts and the checks alike (`totals.tally`).
**Example:** `example/suite/ledger_kinds.py`.

### Step 5. Register a report profile

Titles in human terms, sections in reading order, and a facts strip ("what this run
actually did") computed from the ledger.
**Example:** `example/suite/profile.py`.

### Step 6. Describe your email

Pick a `MailClient` (the example uses the Mailpit adapter), and describe your
product's tracker URL shapes (`TrackerPatterns`) and unsubscribe standard
(`UnsubscribeStandard`).
**Example:** `TRACKERS` and `UNSUBSCRIBE` in `example/suite/app_client.py`; the
`inbox` fixture in `example/suite/conftest.py`.

### Step 7. Fixtures: sign-in, browser evidence, recording, cleanup

- A session fixture that fails loudly when the product is unreachable.
- Browser contexts built by hand (to reuse a session) get `framework.ui.tracing.Evidence`:
  every browser test keeps a video (in the run's `videos/`, linked from the report),
  and the trace and the screen after each UI check are kept only when a UI check
  failed. The context records its video to a temporary folder, removed afterwards.
- A `record` fixture that stamps each ledger entry with the test that wrote it.
- Factories that create run-owned entities and `register_entity` them.
- A session-scoped cleanup that removes `cleanup_targets()` only - a failure's
  entities are preserved as evidence by the plugin.
- `v1`-style fixtures from `api_recorder` for the public API.

**Example:** `example/suite/conftest.py`.

### Step 8. Baseline

Read every surface verification will compare against, before anything acts, and
`snapshot` it into the ledger. A reading's value is the point, so its step says what
it found in words (`found=`): "Newest row is #413", not a bare number.
**Example:** `example/suite/tests/baseline/test_baseline.py`.

### Step 9. Actions

Each action test acts through the UI or API, ends every UI action on its visible
result, and records what it did the moment the system confirms it - on a surface
independent of the one that drove it. Safety guards (`assert_within_cap`,
`assert_owned`) run before anything is sent.

Mark every check of what is on screen `ui=True`, so its screen is evidence when it
fails. Inside every other check, `attach` what it saw before it asserts - the
delivered email for an inbox check, the rows or response for the rest - so a failed
check keeps its own kind of evidence (kept only if that check fails).
**Example:** `example/suite/tests/actions/`, `example/suite/evidence.py`.

### Step 10. Page objects and components

One page object per page; actions end on their result, not their first visible
change. Widgets without roles get a component that says so. Icon-polluted button
names are matched with `label_pattern`.
**Example:** `example/suite/pages/`, `example/suite/components/`.

### Step 11. Verification

Poll each asynchronous surface for the real condition within a budget
(`poll_until`), then reconcile exactly against the ledger: sets, not counts
(`framework.pipeline.sets`); rolling windows decided per action
(`framework.pipeline.windows`); policy observed, not asserted
(`framework.pipeline.expectations`). A check never passes on nothing: an empty
expected set fails unless empty is the point, and nothing to check is recorded as
not run. Each reconciliation attaches the rows or report it read, as its evidence.
**Example:** `example/suite/tests/verification/`.

### Step 12. API tests and docs coverage

Drive the public API through `api_recorder`: every call and check is a soft step, and
the plugin fails a test that ends holding a failed one. Let a smoke test walk the
product's own endpoint index, write full tests for what needs data, and finish the
session with the docs-coverage check against that same index.
**Example:** `example/suite/tests/api/`, `example/suite/tests/verification/test_api_docs.py`.

### Step 13. Prove every test can fail

For each test, a switch in the product that injects the defect it guards, and a bug
matrix naming the test, the check that must go red, and any other test the defect is
known to reach, with the reason. A checker holds each run to it, so an unexplained red
is reported as a separate defect. CI runs the clean product (must be green) and every
switch (each red at its guard).
**Example:** `example/app/bugs.py`, `example/suite/bug_matrix.py`,
`scripts/check_flag_run.py`, `.github/workflows/ci.yml`.

### Step 14. One command

A compose file that starts the product, its dependencies, an inbox and the test
runner, and returns pytest's exit code with `--exit-code-from tests`. The report is
mailed to the inbox as well as written to disk, and `reports/latest.html` always
opens the newest.
**Example:** `docker-compose.yml`, `example/suite/Dockerfile`.
