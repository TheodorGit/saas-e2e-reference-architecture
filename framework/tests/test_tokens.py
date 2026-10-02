import os
import re
from datetime import datetime

import pytest

from framework import tokens

pytestmark = pytest.mark.unit


def test_run_id_is_readable_time_plus_suffix():
    run_id = tokens.new_run_id(datetime(2026, 9, 30, 14, 12))
    assert re.fullmatch(r"0930_1412[0-9a-f]{4}", run_id)


def test_tokens_are_unique_and_carry_the_run(monkeypatch):
    monkeypatch.setenv("E2E_NAME_PREFIX", "QA")
    first = tokens.subject_token("0930_1412abcd", "send")
    second = tokens.subject_token("0930_1412abcd", "send")
    assert first != second
    assert first.startswith("QA-0930_1412abcd-send-")


def test_shorten_keeps_only_each_tokens_slug(monkeypatch):
    monkeypatch.setenv("E2E_NAME_PREFIX", "QA")
    entity = tokens.entity_name("1001_1320ae98", "unsub-oneclick")
    subject = tokens.subject_token("1001_1320ae98", "send")
    address = f"qa+{entity.lower()}@example.com"
    assert tokens.shorten(f"{address}: unsubscribe as click") == \
        "unsub-oneclick: unsubscribe as click"
    assert tokens.shorten(f"rows tagged {entity} for {subject}") == \
        "rows tagged unsub-oneclick for send"
    assert tokens.shorten("the email they received") == "the email they received"


def test_run_dir_honours_results_root(monkeypatch, tmp_path):
    monkeypatch.setenv("E2E_RESULTS_DIR", str(tmp_path))
    path = tokens.run_dir()
    assert path.parent == tmp_path and path.is_dir()


def test_the_run_folder_carries_its_label(monkeypatch, tmp_path):
    monkeypatch.setenv("E2E_RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("E2E_RUN_LABEL", "suppression_leak")
    assert tokens.run_dir().name == f"{tokens.current_run_id()}-suppression_leak"
    monkeypatch.delenv("E2E_RUN_LABEL")
    assert tokens.run_dir().name == tokens.current_run_id()


def test_newest_run_is_the_newest_finished_one_with_exactly_that_label(tmp_path):
    def run(name, finished_at=None):
        folder = tmp_path / name
        folder.mkdir()
        if finished_at is not None:
            (folder / "manifest.json").write_text("{}")
            os.utime(folder / "manifest.json", (finished_at, finished_at))
    run("1001_0900aaaa-clean", 1000)
    run("1001_1000bbbb-clean", 2000)
    run("1001_1100cccc-suppression_leak", 3000)
    run("1001_1200dddd-clean")  # still running: no manifest yet
    assert tokens.newest_run(tmp_path, "clean") == tmp_path / "1001_1000bbbb-clean"
    assert tokens.newest_run(tmp_path, "suppression_leak") == \
        tmp_path / "1001_1100cccc-suppression_leak"
    assert tokens.newest_run(tmp_path, "leak") is None
