"""The plugin end to end: a throwaway suite run through pytest in a subprocess."""
import json

import pytest

from framework import pytest_plugin

pytestmark = pytest.mark.unit

CONFTEST = """
pytest_plugins = ["framework.pytest_plugin"]

from framework.reporting import profiles
profiles.register(profiles.SuiteProfile(
    key="toy", path_prefix="", title="Toy run",
    sections=[("All", ["test_baseline", "test_action", "test_verify"])]))
"""

INI = """
[pytest]
e2e_stages =
    z_baseline/ = 0
    a_verification/ = 2
"""

ORDER_LOG = "order.log"


def _logging_test(name, body=""):
    return (f"from pathlib import Path\n"
            f"def {name}(checks, e2e_ledger):\n"
            f"    Path('{ORDER_LOG}').open('a').write('{name}\\n')\n{body}")


@pytest.fixture
def toy_suite(pytester, monkeypatch):
    monkeypatch.setenv("E2E_RESULTS_DIR", str(pytester.path / "reports"))
    monkeypatch.delenv("E2E_RUN_LABEL", raising=False)
    monkeypatch.delenv("E2E_ALLOW_DESTRUCTIVE", raising=False)
    monkeypatch.delenv("E2E_REPORT_TO", raising=False)
    pytester.makeconftest(CONFTEST)
    pytester.makeini(INI)
    pytester.mkpydir("a_verification").joinpath("test_v.py").write_text(_logging_test(
        "test_verify",
        "    checks.check('totals', lambda: (_ for _ in ()).throw(AssertionError('off by one')),\n"
        "               'Totals match the run')\n"))
    pytester.mkpydir("m_actions").joinpath("test_a.py").write_text(_logging_test(
        "test_action",
        "    e2e_ledger.register_entity('draft', 'd1', 'draft one')\n"
        "    checks.check('send', lambda: 3, 'Three sent')\n"))
    pytester.mkpydir("z_baseline").joinpath("test_b.py").write_text(_logging_test(
        "test_baseline"))
    pytester.makepyfile(test_danger="""
import pytest
@pytest.mark.destructive
def test_danger():
    raise RuntimeError('must never run without the opt-in')
""")
    def run(*args):
        result = pytester.runpytest_subprocess("-p", "no:cacheprovider", *args)
        reports = pytester.path / "reports"
        found = [p for p in reports.iterdir() if p.is_dir()] if reports.exists() else []
        return pytester, result, (found[0] if found else None)
    return run


@pytest.fixture
def toy_run(toy_suite):
    return toy_suite()


def test_stages_order_the_run_regardless_of_file_order(toy_run):
    pytester, _, _ = toy_run
    order = (pytester.path / ORDER_LOG).read_text().split()
    assert order == ["test_baseline", "test_action", "test_verify"]


def test_destructive_tests_are_skipped_without_the_opt_in(toy_run):
    _, result, _ = toy_run
    result.assert_outcomes(passed=2, failed=1, skipped=1)


def test_the_manifest_and_reports_are_written(toy_run):
    _, _, run_dir = toy_run
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["interrupted"] is False
    statuses = {t["func"]: t["status"] for t in manifest["tests"]}
    assert statuses == {"test_baseline": "passed", "test_action": "passed",
                        "test_verify": "failed", "test_danger": "skipped"}
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["verdict"] == "failed" and summary["suite_title"] == "Toy run"
    report = (run_dir / "report.html").read_text()
    assert "Totals match the run" in report and "off by one" in report


def test_the_run_names_its_report_by_a_usable_path_and_updates_latest(toy_run):
    pytester, result, run_dir = toy_run
    relative = f"reports/{run_dir.name}/report.html"
    result.stdout.fnmatch_lines([f"[[]report[]] {relative}",
                                 "[[]report[]] latest: reports/latest.html"])
    latest = (pytester.path / "reports" / "latest.html").read_text()
    assert f"url={run_dir.name}/report.html" in latest


def test_a_failure_preserves_the_runs_entities(toy_run):
    _, _, run_dir = toy_run
    ledger = json.loads((run_dir / "ledger.json").read_text())
    assert ledger["entities"][0]["preserve"] is True


def test_a_whole_run_says_that_every_test_was_selected(toy_run):
    _, _, run_dir = toy_run
    assert json.loads((run_dir / "selection.json").read_text()) == {
        "collected": 4, "selected": 4, "deselected": 0, "expression": ""}
    assert "All 4 tests in the suite selected" in (run_dir / "report.html").read_text()


def test_a_narrowed_run_says_what_it_left_out(toy_suite):
    _, result, run_dir = toy_suite("-k", "verify")
    result.assert_outcomes(failed=1, deselected=3)
    selection = json.loads((run_dir / "selection.json").read_text())
    assert selection == {"collected": 4, "selected": 1, "deselected": 3,
                         "expression": '-k "verify"'}
    sentence = "1 of 4 tests selected - 3 deselected by -k &quot;verify&quot;"
    for page in ("report.html", "email.html"):
        assert sentence in (run_dir / page).read_text(), f"{page} does not say what ran"
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["selection"]["sentence"] == '1 of 4 tests selected - 3 deselected by -k "verify"'


def test_a_collection_leaves_no_run_behind(toy_suite):
    _, result, run_dir = toy_suite("--collect-only")
    result.assert_outcomes()
    assert run_dir is None, f"--collect-only wrote a run directory: {run_dir}"


class _FakeConfig:
    # Complete enough that pytest_configure succeeds on it, so the guard is what refuses.
    def __init__(self, **attributes):
        self.stash = {}
        self.__dict__.update(attributes)

    def addinivalue_line(self, name, line):
        pass


@pytest.fixture
def no_run_id(monkeypatch):
    monkeypatch.setattr(pytest_plugin.tokens, "current_run_id", lambda: "0101_00001111")


def test_a_parallel_worker_is_refused(no_run_id):
    with pytest.raises(pytest.UsageError, match="single-process"):
        pytest_plugin.pytest_configure(_FakeConfig(workerinput={"workerid": "gw0"}))


def test_a_new_session_does_not_inherit_the_last_ones_deselections(no_run_id):
    pytest_plugin._deselected.append(object())
    pytest_plugin.pytest_configure(_FakeConfig())
    assert pytest_plugin._deselected == []


def test_a_single_process_config_is_accepted(no_run_id):
    config = _FakeConfig()
    pytest_plugin.pytest_configure(config)
    assert config.stash
