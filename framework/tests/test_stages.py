from types import SimpleNamespace

import pytest

from framework.pipeline.stages import order_items, parse_stages, stage_of

pytestmark = pytest.mark.unit

STAGES = parse_stages(["suite/baseline/ = 0", "suite/verification/ = 2", "", "# note"])


def test_parse_reads_fragment_and_rank():
    assert STAGES == [("suite/baseline/", 0), ("suite/verification/", 2)]


def test_parse_rejects_a_line_without_rank():
    with pytest.raises(ValueError):
        parse_stages(["suite/baseline/"])


def test_unlisted_paths_take_the_default_rank():
    assert stage_of("suite/actions/test_send.py", STAGES) == 1
    assert stage_of(r"suite\verification\test_totals.py", STAGES) == 2


def test_the_most_specific_stage_wins_whatever_order_the_lines_are_in():
    broad_first = parse_stages(["suite/ = 0", "suite/verification/ = 2"])
    narrow_first = parse_stages(["suite/verification/ = 2", "suite/ = 0"])
    for stages in (broad_first, narrow_first):
        assert stage_of("suite/verification/test_totals.py", stages) == 2
        assert stage_of("suite/actions/test_send.py", stages) == 0


def test_ordering_is_by_stage_and_stable_within_a_stage():
    names = ["verification/a", "actions/b", "baseline/c", "actions/d", "verification/e"]
    items = [SimpleNamespace(path=f"suite/{n}.py", name=n) for n in names]
    order_items(items, STAGES)
    assert [i.name for i in items] == ["baseline/c", "actions/b", "actions/d",
                                       "verification/a", "verification/e"]
