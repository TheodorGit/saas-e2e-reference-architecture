# saas-e2e-reference-architecture

End-to-end tests for a SaaS product. Every page must render, and every action must end
on its visible result - that is the floor. On top of it, the suite proves what the
screen cannot: when it says an email batch went out, it has found each recipient's own
copy in an inbox, checked that the billing journal charged exactly what the run did,
and confirmed that the reports, the API and the dashboard agree with each other and
with the run. And every test is shown to fail: switch a defect on in the example app,
and the test that guards it goes red at the exact check.

![The UI tests running against the example app](docs/images/ui-tests.gif)

## What it tests

- **Email batches** reach exactly their audience minus the address suppression list,
  with a positive control, and every delivered email meets an encoded content standard.
- **An automation sequence**: a tag is added, a delay runs out, the email is sent - and
  a contact who unsubscribed gets nothing.
- **Address validation** is billed exactly once, and free again inside its rolling window.
- **Reports, the API and the dashboard** agree with each other and with the run, by set,
  not by count.
- **The public API**: every documented endpoint is executed, or the build is red.

## See it

- **[Open a live example report](https://TheodorGit.github.io/saas-e2e-reference-architecture/)** -
  a green run and a red one, with the videos and the evidence each failure kept.
  Nothing to install.
- **Try it in your browser** -
  [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/TheodorGit/saas-e2e-reference-architecture?quickstart=1)
  then run the command below in its terminal, and open the forwarded port 7900 to
  watch the tests.
- **Run it locally** - Docker is the only requirement: [how, below](#run-it-locally).

## Run it locally

```
docker compose up --build --exit-code-from tests
```

This starts the example app (the Demo ESP App, a fictional email service provider), its
worker, an inbox and the test runner, runs the suite, and exits with pytest's code: 0
is green, anything else is red.

- **Watch it live** at <http://localhost:7900>: the browser, slowed down so a person can
  follow it. Opening it is optional, and clicking in it cannot disturb a test.
  `E2E_HEADLESS=1` runs at full speed without it.
- **Read the report** at `reports/latest.html` when the run ends. Every browser test has
  a video, and every failed check keeps what it saw: the email, the request and
  response, or the screen. The report is also mailed into the run's inbox and kept next
  to it as `email.html`.

### Break it on purpose

Switch a defect on, and watch the test that guards it go red:

```
# bash
DEMO_ESP_BUGS=suppression_leak docker compose up --build --exit-code-from tests
# PowerShell (the second line switches the defect off again)
$env:DEMO_ESP_BUGS = "suppression_leak"; docker compose up --build --exit-code-from tests
Remove-Item Env:DEMO_ESP_BUGS
```

Try `automation_ignores_unsubscribe` to see the automation email a contact who
unsubscribed. There are 19 defects to choose from, listed in
[`example/app/bugs.py`](example/app/bugs.py); each run's report lands in
`reports/<defect>/`. CI runs the clean app and every one of them on each push: the
clean run must be green, and each defect must go red in the test that guards it, and
nowhere unexplained.

## What a report looks like

Both of these are live, refreshed by CI on every push:
[the green report](https://TheodorGit.github.io/saas-e2e-reference-architecture/green/report.html)
and [the red one](https://TheodorGit.github.io/saas-e2e-reference-architecture/red/report.html).

A green run - every action reconciled, and a facts strip saying what the run did:

![A green report](docs/images/report-green.png)

A red run with `suppression_leak` - the guarding test fails at the exact check, saying
what it means, what was expected and what happened instead, next to the email the
suppressed contact received and a video of the test. The leak also reaches billing, the
dashboard and the report, and each says so:

![A red report](docs/images/report-red.png)

## Context

This architecture is distilled from an end-to-end suite I built for Campaign Refinery,
an email-marketing SaaS. It is shared with the company's permission. Everything here
is a clean-room re-implementation: the example app is fictional, and no internal data,
code or product details from the original are included.

---

**For engineers:** [the architecture and how to adopt it](docs/ARCHITECTURE.md),
[case studies](docs/CASE_STUDIES.md) and [running it in detail](docs/RUNNING.md) -
timings, settings, iterating on the suite, CI.
