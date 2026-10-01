# Running in detail

The [README](../README.md#run-it-locally) covers running the suite, watching it and breaking it
on purpose. This is the rest: what happens underneath, how long it takes, the settings,
and how to work on the suite. Nothing needs a real account, key or hand-filled `.env`:
every default is a demo value.

## The live view

The browser runs headed on a virtual screen in the test runner, slowed down
(`E2E_SLOWMO_MS`, default 300 ms per action), and that screen is served at
<http://localhost:7900> - watch-only, so a click there cannot disturb a test. If the
live view cannot start, the run goes on headless and says so. `E2E_HEADLESS=1` skips it
and runs at full speed; CI does.

A watched run ends on its result: after the last test, the live view shows the report
email as it arrived in the inbox, then the full report it attaches, each for
`E2E_SHOW_REPORT_S` seconds (default 30, slowly scrolled; 0 skips it). This is
`example/suite/show_report.py`, run by `entrypoint.sh`; it never changes the run's
outcome.

The containers stop with the run, so the inbox goes with them. The report mailed into
it (to `qa-reports@example.com`, over plain SMTP - never through the app under test) is
kept on disk too, as `email.html` next to the report.

## How long it takes

The first build downloads the Playwright image (browsers included) and installs the
app, which takes a few minutes; Docker caches both, so later runs skip it. To demo it,
run `docker compose build` beforehand. Measured on a Windows laptop with Docker Desktop:

| Run | Time |
|---|---|
| Clean, with the live view (the default; slowed down to be watched) | about 90 s |
| Clean, headless | about 60 s |
| A defect switched on, headless | 1 to 2 minutes |

A red run takes longer because some checks wait for something that never comes: "not
arrived yet" and "never arriving" look the same until the waiting budget runs out. A
clean run never waits that long - every wait returns as soon as its condition holds.

## Settings

Read by `docker-compose.yml`; set them in the shell before `docker compose up`.

| Variable | Default | What it does |
|---|---|---|
| `DEMO_ESP_INGEST_DELAY_S` | 5 | Stats and billing land this long after the event |
| `DEMO_ESP_VALIDATION_FREE_WINDOW_S` | 20 | Re-validating an address inside this window is free; the suite waits it out once |
| `DEMO_ESP_UI_LATENCY_MS` | 300 | Simulated server latency on the app's read endpoints |
| `DEMO_ESP_BUGS` | (none) | Defects to inject, comma-separated; an unknown name stops the app at start-up |
| `E2E_HEADLESS` | 0 | `1` runs the browser headless, without the live view |
| `E2E_SLOWMO_MS` | 300 | How much each browser action is slowed down in the live view |
| `E2E_SHOW_REPORT_S` | 30 | How long a watched run shows its report email, then its report; 0 skips it |
| `E2E_MAIL_BUDGET_S` | 20 | How long the suite waits for an email to arrive |
| `E2E_INGEST_BUDGET_S` | 20 | How long the suite waits for stats and billing to land |

The two budgets are sized to the demo app, where mail arrives in about a second and
stats in `DEMO_ESP_INGEST_DELAY_S`. Pointed at a real product, the suite's own default
is 60 s each (`example/suite/config.py`, with `E2E_MAX_WINDOW_WAIT_S` and
`E2E_AUDIENCE_CAP`).

## Holding a run to the bug matrix

Which test must catch each defect is `example/suite/bug_matrix.py`. To hold a finished
run to it (needs Python 3.11+ on the host and `pip install -e .`):

```
python scripts/check_flag_run.py reports/clean
python scripts/check_flag_run.py reports/suppression_leak --flag suppression_leak
```

It sorts every red test into the flag's guard (red at its declared check), a declared
impact of the flag (with the reason), or a SEPARATE DEFECT - which fails the check -
and writes the verdict to `matrix_check.txt` next to the report.

## Iterating on the suite

Keep the stack up and run pytest in the runner with the working tree mounted, so edits
apply without rebuilding:

```
docker compose up -d --build demo-esp worker mailpit
docker compose run --rm -v "${PWD}:/srv" tests python -m pytest example/suite -k validate
```

The app is at <http://localhost:8000> (sign in as `demo@demo-esp.test` /
`demo-esp-password`), the inbox at <http://localhost:8025>; the public API index is
<http://localhost:8000/v1/>, and its token is `demo-api-token`.

Stop and forget everything, database included:

```
docker compose down -v
```

## Framework tests

No Docker needed; the one live test against Mailpit skips (and says so) when none is
reachable.

```
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Windows; bin/python elsewhere
.venv/Scripts/pre-commit install
.venv/Scripts/python -m pytest framework/tests
```

## Reports

Each run writes one folder, `reports/<clean or flags>/run_<id>/`:

| File | What |
|---|---|
| `report.html` | Full detail; failures open, passes collapsed |
| `email.html` | The mailed body: failures first, mail-client-safe markup |
| `summary.json` | Machine-readable verdict and counts |
| `manifest.json` | The authority on which tests ran and how each ended |
| `ledger.json` | What the run did, spent and created |
| `steps__*.json` | Every recorded step, per test |
| `videos/` | A video of every browser test, pass or fail, linked from its test in the report |
| `evidence/<test>/` | What each failed check saw, numbered by check: the email for an inbox check, the request and response for an API check, the rows for a reconciliation; for a failed screen check, its screen plus `00_trace.zip` (open with `playwright show-trace`) |
| `matrix_check.txt` | The bug-matrix verdict, when `check_flag_run.py` was run |

## CI

`.github/workflows/ci.yml` runs, in order: a secrets scan; the framework tests (with a
Mailpit service, so the live test runs); the example against a clean app (must be
green); then one run per flag in the bug matrix, in parallel (each must be red at its
guard, with no separate defect). Every run's report folder is uploaded as an artifact,
red or green.

On a push to `main`, once all of that held, a last job publishes the sample-report site
to GitHub Pages: `scripts/build_site.py` copies the clean run and the `suppression_leak`
run whole (report, videos, evidence) and adds a landing page. A red build never
replaces the published site. It needs one repository setting: Settings > Pages >
Source: GitHub Actions. To preview it locally (Windows included):

```
python scripts/build_site.py --green reports/clean --red reports/suppression_leak --out site
python -m http.server -d site
```

## Codespaces

`.devcontainer/` gives a Python 3.12 container with Docker-in-Docker, and opens with
`.devcontainer/START_HERE.md`: the one command to run, and where the live view appears.
Ports 8000 (Demo ESP App) and 8025 (Mailpit) are forwarded; port 7900, the live view
of the UI tests, opens by itself in the editor's built-in browser as soon as a run
starts it (a panel, not a pop-up a browser could block). Port 1025, Mailpit's SMTP, is
for the app only and stays hidden; any other port appears quietly in the Ports tab.
Creating the container installs the project and builds the images (`docker compose
build`), so with a Codespaces prebuild set up on `main` that work is done before
anyone opens one.
