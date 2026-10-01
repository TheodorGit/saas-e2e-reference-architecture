"""The plugin end to end: a throwaway suite run through pytest in a subprocess.

Directory names sort in the WRONG order on purpose (verification first
alphabetically), so a pass proves the stage option, not the file system, set
the order.
"""
import json

import pytest

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
            f"def {name}(steps, e2e_ledger):\n"
            f"    Path('{ORDER_LOG}').open('a').write('{name}\\n')\n{body}")


@pytest.fixture
def toy_run(pytester, monkeypatch):
    monkeypatch.setenv("E2E_RESULTS_DIR", str(pytester.path / "reports"))
    monkeypatch.delenv("E2E_ALLOW_DESTRUCTIVE", raising=False)
    monkeypatch.delenv("E2E_REPORT_TO", raising=False)
    pytester.makeconftest(CONFTEST)
    pytester.makeini(INI)
    pytester.mkpydir("a_verification").joinpath("test_v.py").write_text(_logging_test(
        "test_verify",
        "    steps.step('totals', lambda: (_ for _ in ()).throw(AssertionError('off by one')),\n"
        "               'Totals match the run')\n"))
    pytester.mkpydir("m_actions").joinpath("test_a.py").write_text(_logging_test(
        "test_action",
        "    e2e_ledger.register_entity('draft', 'd1', 'draft one')\n"
        "    steps.step('send', lambda: 3, 'Three sent')\n"))
    pytester.mkpydir("z_baseline").joinpath("test_b.py").write_text(_logging_test(
        "test_baseline"))
    pytester.makepyfile(test_danger="""
import pytest
@pytest.mark.destructive
def test_danger():
    raise RuntimeError('must never run without the opt-in')
""")
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    run_dir = next((pytester.path / "reports").glob("run_*"))
    return pytester, result, run_dir


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
