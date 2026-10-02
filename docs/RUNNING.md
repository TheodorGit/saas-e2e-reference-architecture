# Running in detail

The [README](../README.md#run-it-locally) covers running the suite, watching it and
switching defects on. This page covers the rest. Every setting has a demo default, so no
account, key or `.env` file is needed.

## The live view

The browser runs headed on a virtual screen in the test runner, slowed down by
`E2E_SLOWMO_MS` (default 300 ms per action). The screen is served at
<http://localhost:7900>, view-only. Until the browser tests start, that address shows a
waiting page (`example/suite/live/`). If the live view cannot start, the run continues
headless and says so. `E2E_HEADLESS=1` turns it off; CI does.

After the last test, the live view shows the report email, then the full report, each
for `E2E_SHOW_REPORT_S` seconds (default 30; 0 skips it). This is
`example/suite/show_report.py`, started by `entrypoint.sh`. It does not affect the
run's result.

The inbox stops with the containers. The report is mailed to `qa-reports@example.com`
over plain SMTP, not through the app, and saved as `email.html` next to the report.

## How long it takes

The first build downloads a slim Python image and Chromium and installs the app, which
takes a few minutes. Docker caches it, so later runs skip it. Before a demo, run
`docker compose build`. Measured on a Windows laptop with Docker Desktop:

| Run | Time |
|---|---|
| Clean, with the live view (the default) | about 90 s |
| Clean, headless | about 60 s |
| A defect switched on, headless | 1 to 2 minutes |

A red run is slower because some checks wait for something that never arrives, until
their time budget runs out. A clean run moves on as soon as each condition holds.

## Settings

Set these in the shell before `docker compose up`.

| Variable | Default | What it does |
|---|---|---|
| `DEMO_ESP_INGEST_DELAY_S` | 5 | Stats and billing land this long after the event |
| `DEMO_ESP_VALIDATION_FREE_WINDOW_S` | 20 | Re-validating an address inside this window is free |
| `DEMO_ESP_UI_LATENCY_MS` | 300 | Simulated latency on the app's read endpoints |
| `DEMO_ESP_BUGS` | (none) | Defects to switch on, comma-separated; an unknown name stops the app |
| `E2E_HEADLESS` | 0 | `1` runs the browser headless, without the live view |
| `E2E_SLOWMO_MS` | 300 | Delay per browser action in the live view |
| `E2E_SHOW_REPORT_S` | 30 | How long a watched run shows the report email and the report; 0 skips it |
| `E2E_MAIL_BUDGET_S` | 20 | How long the suite waits for an email |
| `E2E_INGEST_BUDGET_S` | 20 | How long the suite waits for stats and billing |

The two budgets suit the demo app. The suite's own default for a real product is 60 s
each (`example/suite/config.py`, which also has `E2E_MAX_WINDOW_WAIT_S` and
`E2E_AUDIENCE_CAP`).

## Checking a run against the bug matrix

`example/suite/bug_matrix.py` names the test that must catch each defect. To check a
finished run against it (needs Python 3.11+ and `pip install -e .`):

```
python scripts/check_flag_run.py reports
python scripts/check_flag_run.py reports --flag suppression_leak
```

It takes the newest run for that flag (or the newest clean run) and sorts each failed
test into: the flag's guard (failed at its declared check), a declared impact of the
flag, or a separate defect, which fails the check. The result is written to
`matrix_check.txt` next to the report.

## Working on the suite

Keep the app running and run pytest in the runner with the working tree mounted, so
edits apply without a rebuild:

```
docker compose up -d --build demo-esp worker mailpit
docker compose run --rm -v "${PWD}:/srv" tests python -m pytest example/suite -k validate
```

The app is at <http://localhost:8000> (sign in as `demo@demo-esp.test` /
`demo-esp-password`) and the inbox at <http://localhost:8025>. The public API index is
<http://localhost:8000/v1/>, with the token `demo-api-token`.

To stop everything and delete the database:

```
docker compose down -v
```

## Framework tests

These need no Docker. The one test against a real Mailpit is skipped when none is
running.

```
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Windows; bin/python elsewhere
.venv/Scripts/pre-commit install
.venv/Scripts/python -m pytest framework/tests
```

## Reports

Each run writes one folder, `reports/<run id>-<clean or flags>/`. The run id is the date
and time plus a short random part, e.g. `1002_1514ab12-suppression_leak`.

| File | What |
|---|---|
| `report.html` | The full report; failures expanded, passes collapsed |
| `email.html` | The mailed report |
| `summary.json` | Verdict and counts |
| `manifest.json` | Which tests ran and how each ended |
| `ledger.json` | What the run did, spent and created |
| `steps__*.json` | Every recorded step, per test |
| `videos/` | A video of every browser test |
| `evidence/<test>/` | What each failed check saw, named `NN <what it is>.ext` by check number (e.g. `06 the email they received.html`). A failed screen check adds `NN screen.png` and `00 trace.zip` (open with `playwright show-trace`) |
| `evidence/<test>/test.txt` | The test and every check, with its number and result |
| `matrix_check.txt` | The bug-matrix result, when `check_flag_run.py` was run |

## CI

`.github/workflows/ci.yml` runs a secrets scan, the framework tests (with a Mailpit
service), the example against the clean app (must pass), then one run per defect in
parallel (each must fail at its guard, with no separate defect). Every run's report
folder is uploaded as an artifact.

On a push to `main`, after all of that passes, the last job publishes the sample-report
site to GitHub Pages: `scripts/build_site.py` copies the clean run and the
`suppression_leak` run and adds a landing page. A failed build leaves the published site
as it was. It needs Settings > Pages > Source: GitHub Actions. To preview it locally:

```
python scripts/build_site.py --reports reports --red suppression_leak --out site
python -m http.server -d site
```

## Codespaces

`.devcontainer/` is a Python 3.12 container with Docker-in-Docker. It opens
`.devcontainer/START_HERE.md`, which has the command to run. Ports 8000 (the app) and
8025 (Mailpit) are forwarded without a notification. Port 7900, the live view, shows a
notification with an Open in Browser button when a run starts; the button is a click,
so browsers do not block the new tab. The notification can come before the browser
tests start, which is why 7900 shows a waiting page until then. Port 1025 (Mailpit's
SMTP) is not forwarded.

Creating the container installs the project and builds the images, so with a
Codespaces prebuild on `main` that work is done before anyone opens one.
