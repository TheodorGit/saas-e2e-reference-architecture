"""The framework's pytest plugin: its hooks and fixtures."""
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
        # Relative, so the path works on the host and inside a container that mounts it.
        print(f"\n[report] {built['subject']}\n[report] {_shown(built['report'])}\n"
              f"[report] latest: {_shown(latest)}")
    except Exception as exc:  # a report bug must not change the run's outcome
        print(f"\n[report] could not build reports: {exc}")
        return
    from framework.reporting.mailer import send_report
    send_report(directory)


def latest_page() -> Path:
    return Path(os.getenv(LATEST_PAGE_ENV) or tokens.results_root() / "latest.html")


def _shown(path) -> str:
    try:
        return Path(os.path.relpath(path)).as_posix()
    except ValueError:  # another drive on Windows: nothing relative to show
        return str(path)


@pytest.fixture(scope="session")
def run_id() -> str:
    return tokens.current_run_id()


@pytest.fixture
def subject_token(run_id, request):
    def make(slug: str = None) -> str:
        return tokens.subject_token(
            run_id, slug or request.node.originalname.removeprefix("test_")[:24])
    return make


@pytest.fixture
def entity_name(run_id):
    return lambda slug: tokens.entity_name(run_id, slug)


@pytest.fixture
def steps(request):
    """Fails the test in teardown if it holds a failed soft step."""
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
    evidence.save_attachments(recorder, tokens.run_dir())
    if call is not None and call.passed:
        recorder.raise_soft_failures()


@pytest.fixture(scope="session")
def api_coverage(request) -> Coverage:
    return request.config.stash[_coverage_key]


@pytest.fixture
def api_recorder(steps, api_coverage, request):
    def make(http, base_url: str, label: str = "") -> ApiRecorder:
        return ApiRecorder(http, base_url, steps, api_coverage, request.node.nodeid, label)
    return make


@pytest.fixture(scope="session")
def e2e_ledger(request):
    path = tokens.run_dir() / "ledger.json"
    source = replay_source(REPLAY_LEDGER_ENV)
    ledger = Ledger.replay(source, path) if source else Ledger(path)
    request.config.stash[_ledger_key] = ledger
    yield ledger
    ledger.save()
