"""Which test must catch each injected defect, and what else each one breaks."""
from typing import NamedTuple


class Guard(NamedTuple):
    test: str
    check: str
    impact: dict = {}


GUARDS = {
    "suppression_leak": Guard(
        "test_email_batch_send_with_suppression", "the suppressed contact got nothing",
        impact={
            "test_billing_journal_reconciles":
                "the leaked copy is billed: 3 credits where the run sent 2",
            "test_report_cards_list_and_api_agree":
                "the report counts the leaked recipient as delivered",
            "test_dashboard_deltas": "the balance drops by the leaked copy's credit too",
        }),
    "double_billing": Guard(
        "test_billing_journal_reconciles", "one row per billable action",
        impact={"test_dashboard_deltas": "the balance drops by the second charge too"}),
    "report_undercount": Guard("test_report_cards_list_and_api_agree", "API delivered_to"),
    "missing_one_click_post": Guard("test_content_standard", "one-click unsubscribe headers"),
    "literal_template_variable": Guard("test_content_standard",
                                       "template variables rendered"),
    "no_list_refresh": Guard("test_bulk_tag_live_refresh", "bulk add a tag"),
    "export_ignores_filter": Guard("test_export_follows_the_filter",
                                   "the export holds exactly the filtered contacts"),
    "unsubscribe_counts_click": Guard("test_unsubscribe_is_not_engagement",
                                      "unsubscribe as click"),
    "login_accepts_any_password": Guard("test_login", "wrong password is refused"),
    "free_window_ignored": Guard(
        "test_validate_single_address", "validation 2 (again at once): free",
        impact={
            "test_billing_journal_reconciles":
                "the re-validation inside the window is billed 5 where the run expects 0",
            "test_dashboard_deltas": "the balance drops by that extra charge too",
        }),
    "contact_names_swapped": Guard("test_add_contact", "fields stored as entered"),
    "delete_not_persisted": Guard("test_ui_delete", "delete through the UI"),
    "resubscribe_ignored": Guard("test_unsubscribe_and_resubscribe",
                                 "the API shows it subscribed again"),
    "api_ignores_auth": Guard("test_api_smoke", "without a token: GET"),
    "api_contact_tags_dropped": Guard("test_api_contact_lifecycle", "created as sent"),
    "api_validation_reports_zero_cost": Guard("test_api_validation_is_billed",
                                              "the response states the charge"),
    "api_balance_stale": Guard("test_api_reads_agree", "balance agrees with the app"),
    "api_endpoint_without_test": Guard("test_documented_endpoints_were_exercised",
                                       "every documented endpoint was executed this session"),
    "automation_ignores_unsubscribe": Guard("test_automation_skips_unsubscribed",
                                            "the unsubscribed contact got nothing"),
}

NOT_GUARDED = {
    "test_baseline_readings": "reads the surfaces before the run acts; guards nothing alone",
    "test_dashboard_deltas": "proven red as the declared impact of every billing defect "
                             "(suppression_leak, double_billing, free_window_ignored)",
}
