"""How the Demo ESP App suite presents itself in the framework's report."""
import json
from pathlib import Path

from example.suite import ledger_kinds as kinds
from framework.reporting.profiles import SuiteProfile, register

SECTIONS = [
    ("Baseline", ["test_baseline_readings"]),
    ("Actions", [
        "test_login", "test_validate_single_address", "test_add_contact", "test_ui_delete",
        "test_bulk_tag_live_refresh", "test_export_follows_the_filter",
        "test_email_batch_send_with_suppression", "test_content_standard",
        "test_unsubscribe_and_resubscribe", "test_automation_skips_unsubscribed",
    ]),
    ("Public API", [
        "test_api_smoke", "test_api_contact_lifecycle", "test_api_validation_is_billed",
        "test_api_reads_agree",
    ]),
    ("Verification", [
        "test_billing_journal_reconciles", "test_dashboard_deltas",
        "test_report_cards_list_and_api_agree", "test_unsubscribe_is_not_engagement",
        "test_documented_endpoints_were_exercised",
    ]),
]

TITLES = {
    "test_baseline_readings": "Baseline readings before the run acts",
    "test_login": "Sign in, and a wrong password is refused",
    "test_validate_single_address":
        "Validate one address: billed, free inside the window, billed after",
    "test_add_contact": "Add a contact through the UI",
    "test_ui_delete": "Delete a contact through the UI",
    "test_bulk_tag_live_refresh": "Bulk tag and untag; the list shows the server's truth",
    "test_export_follows_the_filter": "Export holds exactly the filtered contacts",
    "test_email_batch_send_with_suppression":
        "Email batch to a tag, with an address suppression list and a positive control",
    "test_content_standard": "Delivered email meets the content standard",
    "test_unsubscribe_and_resubscribe": "Unsubscribe and resubscribe: public page and one-click",
    "test_automation_skips_unsubscribed":
        "Automation: a tag starts a delayed email; an unsubscribed contact gets nothing",
    "test_billing_journal_reconciles": "Billing journal reconciles exactly with the run",
    "test_dashboard_deltas": "Dashboard moved by exactly what the run did",
    "test_report_cards_list_and_api_agree": "Report cards, drill-down lists and API agree",
    "test_unsubscribe_is_not_engagement": "Unsubscribing is not counted as engagement",
    "test_api_smoke": "API smoke: every documented read, with and without a token",
    "test_api_contact_lifecycle": "API: a contact created, read, found, refused, deleted",
    "test_api_validation_is_billed": "API: validation is billed, and the response says so",
    "test_api_reads_agree": "API reads agree with the app",
    "test_documented_endpoints_were_exercised":
        "Every documented API endpoint was executed this session",
}


def facts(run_dir: Path, _tests: list) -> list:
    path = Path(run_dir) / "ledger.json"
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    spent = kinds.spend(entries)
    sends = [e for e in entries if e["kind"] in kinds.SENDS]
    mailed = [e for e in entries if e["kind"] in (*kinds.SENDS, kinds.AUTOMATION)]
    return [
        ("credits charged", spent["total"]),
        ("emails sent", sum(len(e.get("recipients") or []) for e in mailed)),
        ("opens fired", sum(len(e.get("opened") or []) for e in sends)),
        ("clicks fired", sum(len(e.get("clicked") or []) for e in sends)),
        ("addresses validated", sum(1 for e in entries if e["kind"] == kinds.VALIDATION)),
    ]


PROFILE = register(SuiteProfile(
    key="demo_esp", path_prefix="example/suite/", title="Demo ESP App end-to-end run",
    sections=SECTIONS, titles=TITLES, facts=facts,
    passed_subhead="Every action below was reconciled on a surface independent of the "
                   "one that drove it."))
