"""The framework as a pytest plugin. A suite enables it with

    pytest_plugins = ["framework.pytest_plugin"]

and gets:
  hooks     stage ordering (ini option e2e_stages), the run manifest, report
            build + mail at session end (every run), destructive-test gating,
            replay announced in the header
  fixtures  run_id, subject_token, entity_name,
            steps (a StepRecorder; held soft failures are raised in teardown),
            e2e_ledger (the session ledger, or a replayed one),
            api_recorder (factory; every call and check a soft step),
            api_coverage (every API call this session, for docs coverage)

Artifacts land in reports/run_<run_id>/ (E2E_RESULTS_DIR overrides the root), and
reports/latest.html always opens the newest report (E2E_LATEST_PAGE overrides).
"""
import os
from pathlib import Path

import pytest

from framework import tokens
from framework.api.recorder import ApiRecorder, Coverage
from framework.pipeline.ledger import Ledger
from framework.pipeline.manifest import RunManifest
from framework.pipeline.replay import header_lines, replay_source
from framework.pipeline.stages import order_items, parse_stages
from framework.reporting import evidence, profiles
from framework.reporting.recorder import StepRecorder
from framework.safety.guards import DESTRUCTIVE_ENV, destructive_allowed

REPLAY_LEDGER_ENV = "E2E_REPLAY_LEDGER"
LATEST_PAGE_ENV = "E2E_LATEST_PAGE"

_manifest_key = pytest.StashKey[RunManifest]()
_ledger_key = pytest.StashKey[Ledger]()
_coverage_key = pytest.StashKey[Coverage]()


def pytest_addoption(parser):
    parser.addini("e2e_stages", type="linelist", default=[],
                  help="'path/fragment/ = rank' lines; lower ranks run first")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "destructive: changes controlled resources; runs only with "
                   f"{DESTRUCTIVE_ENV}=1")
    config.stash[_manifest_key] = RunManifest(tokens.current_run_id(),
                                              os.getenv("E2E_ENVIRONMENT"))
    config.stash[_coverage_key] = Coverage()


def pytest_report_header(config):
    source = replay_source(REPLAY_LEDGER_ENV)
    return header_lines("LEDGER", source) if source else None


def pytest_collection_modifyitems(config, items):
    order_items(items, parse_stages(config.getini("e2e_stages")))
    if not destructive_allowed():
        skip = pytest.mark.skip(reason=f"destructive: set {DESTRUCTIVE_ENV}=1 to run")
        for item in items:
            if "destructive" in item.keywords:
                item.add_marker(skip)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    # Exposed so fixtures can read the outcome in teardown.
    setattr(item, f"rep_{report.when}", report)
    manifest = item.config.stash[_manifest_key]
    manifest.record(report, item.originalname or item.name)
    # Rewritten every phase: a killed run still leaves an honest manifest.
    manifest.write(tokens.run_dir(), final=False)
    if report.failed and _ledger_key in item.config.stash:
        # A failure anywhere freezes every entity the run created: evidence.
        item.config.stash[_ledger_key].preserve_all()


def pytest_sessionfinish(session, exitstatus):
    manifest = session.config.stash.get(_manifest_key, None)
    if manifest is None or not manifest.tests:
        return
    directory = tokens.run_dir()
    manifest.write(directory, final=True)
    try:
        from framework.reporting.report_builder import build, write_latest
        built = build(directory)
        latest = write_latest(built["report"], latest_page())
        # Paths relative to where the run started: usable on the host as well
        # as inside a container that mounts the same folder.
        print(f"\n[report] {built['subject']}\n[report] {_shown(built['report'])}\n"
              f"[report] latest: {_shown(latest)}")
    except Exception as exc:  # a report bug must not change the run's outcome
        print(f"\n[report] could not build reports: {exc}")
        return
    from framework.reporting.mailer import send_report
    send_report(directory)


def latest_page() -> Path:
    """The page that always opens the newest report (E2E_LATEST_PAGE overrides)."""
    return Path(os.getenv(LATEST_PAGE_ENV) or tokens.results_root() / "latest.html")


def _shown(path) -> str:
    try:
        return Path(os.path.relpath(path)).as_posix()
    except ValueError:  # another drive on Windows: nothing relative to show
        return str(path)


# --- fixtures ---------------------------------------------------------------

@pytest.fixture(scope="session")
def run_id() -> str:
    return tokens.current_run_id()


@pytest.fixture
def subject_token(run_id, request):
    """Factory: a unique subject token for this test (slug defaults to its name)."""
    def make(slug: str = None) -> str:
        return tokens.subject_token(
            run_id, slug or request.node.originalname.removeprefix("test_")[:24])
    return make


@pytest.fixture
def entity_name(run_id):
    """Factory: a unique, prefixed name for something the test creates."""
    return lambda slug: tokens.entity_name(run_id, slug)


@pytest.fixture
def steps(request):
    """A StepRecorder for this test, finalised with the test's real outcome.

    A test whose body passed while holding a failed soft step is failed here, in
    teardown: raising held failures is not left to the test, so it can never pass
    that way."""
    nodeid = request.node.nodeid
    recorder = StepRecorder(profiles.profile_for(nodeid).key, nodeid)
    yield recorder
    setup = getattr(request.node, "rep_setup", None)
    call = getattr(request.node, "rep_call", None)
    skipped = (setup is not None and setup.skipped) or (call is not None and call.skipped)
    if skipped:
        recorder.finalize("skipped")
    else:
        recorder.finalize("completed" if call is not None and call.passed else "failed")
    recorder.save(tokens.run_dir())
    # What each failed check saw; a passing check's attachments are dropped.
    evidence.save_attachments(recorder, tokens.run_dir())
    if call is not None and call.passed:
        recorder.raise_soft_failures()


@pytest.fixture(scope="session")
def api_coverage(request) -> Coverage:
    """Every API call recorded this session, keyed by route template."""
    return request.config.stash[_coverage_key]


@pytest.fixture
def api_recorder(steps, api_coverage, request):
    """Factory: make(http_session, base_url, label='') -> ApiRecorder.

    Calls and checks are soft steps on this test's `steps`, whose teardown fails
    a test that passed its body while holding a failed step."""
    def make(http, base_url: str, label: str = "") -> ApiRecorder:
        return ApiRecorder(http, base_url, steps, api_coverage, request.node.nodeid, label)
    return make


@pytest.fixture(scope="session")
def e2e_ledger(request):
    """This run's ledger, or an earlier run's when E2E_REPLAY_LEDGER is set."""
    path = tokens.run_dir() / "ledger.json"
    source = replay_source(REPLAY_LEDGER_ENV)
    ledger = Ledger.replay(source, path) if source else Ledger(path)
    request.config.stash[_ledger_key] = ledger
    yield ledger
    ledger.save()
