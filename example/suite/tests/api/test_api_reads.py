"""The public API's reads agree with the app's own surfaces."""
import pytest

from example.suite import ledger_kinds as kinds

pytestmark = pytest.mark.api

UNKNOWN_ID = 999_999_999


def test_api_reads_agree(v1, app_api, e2e_ledger, steps):
    credits = v1.call("GET", "/v1/credits")
    if credits is not None and credits.status_code == 200:
        body = credits.json()
        v1.check("balance agrees with the app",
                 lambda: _equal(body["balance"], app_api.credits()["balance"],
                                "public API balance vs the app's"),
                 expected="the same balance the signed-in app shows",
                 means="API clients see a different balance than the app.")
        if body["journal"]:
            v1.check("journal rows are well-formed", lambda: _rows(body["journal"]),
                     expected="every row has an id, action, reference and whole credits")
        else:
            steps.skip_step("journal rows are well-formed", "the journal has no rows yet",
                            expected="every row has an id, action, reference and whole credits")

    lists = v1.call("GET", "/v1/address-suppression-lists")
    if lists is not None and lists.status_code == 200:
        mine = {s["name"]: s["size"]
                for s in app_api.call("GET", "/api/address-suppression-lists")}
        v1.check("address suppression lists agree with the app",
                 lambda: _equal({s["name"]: s["size"] for s in lists.json()}, mine,
                                "lists and sizes"),
                 expected="the same lists, with the same sizes")

    v1.call("GET", "/v1/email-batches")
    sent = [e for e in e2e_ledger.entries if e["kind"] in kinds.SENDS and e.get("batch_id")]
    if sent:
        report = v1.call("GET", "/v1/email-batches/{batch_id}/report",
                         batch_id=sent[0]["batch_id"])
        if report is not None and report.status_code == 200:
            v1.check("report counts are their lists' lengths", lambda: _counts(report.json()),
                     expected="delivered, opens and clicks equal the lengths of their lists")
    else:
        steps.skip_step("a report read", "this session sent no email batch to read",
                        expected="a report whose counts match its lists")
    v1.call("GET", "/v1/email-batches/{batch_id}/report", expect=404,
            name="an unknown email batch is 404", batch_id=UNKNOWN_ID)


def _equal(got, want, what: str):
    assert got == want, f"{what}: {got} != {want}"


def _rows(rows: list):
    bad = [r for r in rows if not (isinstance(r.get("id"), int) and r.get("action")
                                  and r.get("reference") and isinstance(r.get("credits"), int))]
    assert not bad, f"malformed journal rows: {bad[:3]}"
    return len(rows)


def _counts(report: dict):
    for count, listed in (("delivered", "delivered_to"), ("opens", "opened_by"),
                          ("clicks", "clicked_by")):
        assert report[count] == len(report[listed]), f"{count} {report[count]} vs " \
                                                     f"{len(report[listed])} listed"
