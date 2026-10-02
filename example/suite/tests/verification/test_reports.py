"""Report cards, drill-down lists and the public API agree with each other and with the run."""
import pytest

from example.suite import evidence
from example.suite import ledger_kinds as kinds
from example.suite.pages.report import ReportPage
from framework.pipeline.sets import assert_partition, assert_same
from framework.polling import poll_until

pytestmark = pytest.mark.pipeline

SURFACES = {"delivered": ("delivered", "delivered_to", "recipients"),
            "opens": ("opens", "opened_by", "opened"),
            "clicks": ("clicks", "clicked_by", "clicked")}
# A send may engage nobody, so these may be empty; a delivered list never may.
ENGAGEMENT = ("opens", "clicks")


def test_report_cards_list_and_api_agree(app_page, public_api, e2e_ledger, config, steps):
    sends = [e for e in e2e_ledger.entries if e["kind"] == kinds.SEND]
    if not sends:
        pytest.skip("no email batch to cross-check")
    page = ReportPage(app_page)

    for entry in sends:
        name = entry["name"]
        want = {card: sorted(entry.get(field) or []) for card, (_, _, field) in SURFACES.items()}

        def matches(report, want=want):
            return all(sorted(report[listed]) == want[card]
                       for card, (_, listed, _) in SURFACES.items())
        api, waited = poll_until(lambda entry=entry: public_api.report(entry["batch_id"]),
                                 matches, config.ingest_budget_s, 2)

        def seen(check, api=api, entry=entry):
            def run():
                evidence.data(steps, "the report the API returned",
                              {"report": api, "the run engaged": {
                                  f: entry.get(f) for f in ("recipients", "suppressed",
                                                            "opened", "clicked")}})
                return check()
            return run

        for card, (count, listed, _) in SURFACES.items():
            steps.soft_step(f"{name}: API {listed}",
                            seen(lambda card=card, listed=listed, api=api, want=want, w=waited:
                            assert_same(want[card], api[listed],
                                        f"{listed} ({w:.0f}s allowed to land)",
                                        allow_empty=card in ENGAGEMENT)),
                            expected=f"{len(want[card])}: exactly who the run engaged",
                            means="The report does not match what happened.")
            steps.soft_step(f"{name}: API {count} is its list's length",
                            seen(lambda count=count, listed=listed, api=api:
                                 _equal(api[count], len(api[listed]), f"{count} vs its list")),
                            expected="a count and its addresses cannot disagree")
        if entry.get("suppressed"):
            steps.soft_step(f"{name}: audience partition",
                            seen(lambda entry=entry, api=api: assert_partition(
                                entry["recipients"] + entry["suppressed"],
                                {"delivered": api["delivered_to"],
                                 "suppressed": entry["suppressed"]})),
                            expected="every audience member delivered or suppressed, "
                                     "never both, never neither")

        page.open(entry["batch_id"], name)
        for card in SURFACES:
            shown = page.card(card)
            listed = page.drill(card)
            steps.soft_step(f"{name}: UI {card} card equals its list",
                            lambda shown=shown, listed=listed, card=card:
                            _equal(shown, len(listed), f"{card} card vs drill-down"),
                            expected="the card's number is the length of its list", ui=True)
            steps.soft_step(f"{name}: UI {card} list",
                            lambda listed=listed, card=card, want=want:
                            assert_same(want[card], listed, f"{card} drill-down",
                                        allow_empty=card in ENGAGEMENT),
                            expected="the drill-down names exactly who the run engaged",
                            ui=True)
    steps.raise_soft_failures()


def _equal(got, want, what: str):
    assert got == want, f"{what}: {got} != {want}"
    return got
