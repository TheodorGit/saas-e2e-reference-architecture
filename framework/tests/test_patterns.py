"""Set-difference, rolling windows, three-valued expectations, icon names."""
from datetime import UTC, datetime, timedelta

import pytest

from framework.delivery.content_checks import list_unsubscribe_targets
from framework.pipeline import sets, windows
from framework.pipeline.expectations import OBSERVE, check
from framework.reporting.recorder import FAILED, PASSED, StepRecorder
from framework.ui.names import label_pattern

pytestmark = pytest.mark.unit


# --- sets ---------------------------------------------------------------------

def test_equal_counts_with_cancelling_errors_are_caught_and_named():
    with pytest.raises(AssertionError) as caught:
        sets.assert_same(["a@x.io", "b@x.io"], ["A@x.io", "c@x.io"], "recipients")
    assert "missing ['b@x.io']" in str(caught.value)
    assert "unexpected ['c@x.io']" in str(caught.value)


def test_same_sets_pass_case_insensitively():
    assert sets.assert_same(["A@x.io"], ["a@x.io"], "recipients").startswith("1 recipients")
    assert sets.difference([1, 2], [2, 3]) == ([1], [3])


def test_disjoint_names_the_overlap():
    with pytest.raises(AssertionError, match="suppressed but delivered: \\['c'\\]"):
        sets.assert_disjoint(["c", "d"], ["a", "c"], "suppressed but delivered")
    assert sets.assert_disjoint(["c"], ["a"], "suppressed but delivered")


@pytest.mark.parametrize("parts, problem", [
    ({"got": ["a", "b"], "held": ["b", "c"]}, "in more than one part: b (got/held)"),
    ({"got": ["a"], "held": ["c"]}, "in no part ['b']"),
    ({"got": ["a", "b", "z"], "held": ["c"]}, "got holds non-members ['z']"),
])
def test_partition_defects(parts, problem):
    with pytest.raises(AssertionError) as caught:
        sets.assert_partition(["a", "b", "c"], parts)
    assert problem in str(caught.value)


@pytest.mark.parametrize("check", [
    lambda: sets.assert_same([], [], "recipients"),
    lambda: sets.assert_same([], ["stranger@x.io"], "recipients"),
    lambda: sets.assert_disjoint([], ["a"], "suppressed but delivered"),
    lambda: sets.assert_partition([], {"got": []}),
])
def test_a_check_over_nothing_fails(check):
    with pytest.raises(AssertionError, match="proves nothing"):
        check()


def test_empty_passes_only_when_it_is_the_point():
    assert sets.assert_same([], [], "rows showing the removed tag", allow_empty=True)
    with pytest.raises(AssertionError, match="unexpected"):
        sets.assert_same([], ["x"], "rows showing the removed tag", allow_empty=True)
    assert sets.assert_disjoint([], ["a"], "free rows billed", allow_empty=True)


def test_a_clean_partition_reports_its_sizes():
    result = sets.assert_partition(["a", "b", "c"], {"got": ["a", "b"], "held": ["c"]})
    assert result == "3 members partitioned: got 2, held 1"


# --- windows ------------------------------------------------------------------

T0 = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("elapsed, expected", [
    (1, True), (7.9, True), (8.5, None), (10, None), (11.9, None), (12.1, False), (-1, None),
])
def test_position_inside_outside_and_too_close_to_call(elapsed, expected):
    at = T0 + timedelta(seconds=elapsed)
    assert windows.position(T0, at, window_s=10, margin_s=2) is expected


def test_no_open_window_is_outside_and_closes_at_is_past_the_margin():
    assert windows.position(None, T0, window_s=10) is False
    closed = windows.closes_at(T0, window_s=10, margin_s=2)
    assert windows.position(T0, closed, window_s=10, margin_s=2) is False


# --- three-valued expectations --------------------------------------------------

def test_true_and_false_are_asserted_observe_is_recorded():
    steps = StepRecorder("t", "t::n")
    assert check(steps, "click", False, False, "unsubscribe counted as a click") is False
    assert check(steps, "open", OBSERVE, True, "one-click counted as an open") is True
    with pytest.raises(AssertionError, match="expected False, observed True"):
        check(steps, "click2", False, True, "unsubscribe counted as a click")
    assert [s["status"] for s in steps.steps] == [PASSED, PASSED, FAILED]
    assert steps.steps[1]["message"].startswith("observed, not asserted")
    assert steps.steps[1]["data"]["observed"] is True


# --- icon-polluted names ---------------------------------------------------------

@pytest.mark.parametrize("name, matches", [
    ("Delete", True), ("delete Delete", True), ("person_add Add contact", True),
    ("delete Delete contact", False), ("Undelete", False), ("x y Delete", False),
])
def test_label_pattern(name, matches):
    label = "Add contact" if "Add" in name else "Delete"
    assert bool(label_pattern(label).match(name)) is matches


def test_list_unsubscribe_targets_reads_without_judging():
    headers = {"list-unsubscribe": "<http://h/u/1>, <mailto:u@x.io>"}
    assert list_unsubscribe_targets(headers) == ["http://h/u/1", "mailto:u@x.io"]
    assert list_unsubscribe_targets({}) == []
