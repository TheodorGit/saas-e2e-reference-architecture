"""Defect switches the suite must catch, set with DEMO_ESP_BUGS."""
import os

FLAGS = {
    "suppression_leak": "address suppression lists are ignored when an email batch is sent",
    "double_billing": "a billed address validation is charged twice",
    "report_undercount": "the email batch report drops one delivered recipient",
    "missing_one_click_post": "emails lack the List-Unsubscribe-Post header",
    "literal_template_variable": "{{first_name}} reaches the inbox unrendered",
    "no_list_refresh": "the contact list keeps its optimistic state after a bulk action",
    "export_ignores_filter": "the CSV export contains every contact, whatever the filter",
    "unsubscribe_counts_click": "an unsubscribe is also counted as a click",
    "login_accepts_any_password": "the demo login accepts any password",
    "free_window_ignored": "re-validating inside the free window is billed again",
    "contact_names_swapped": "the add-contact form sends first and last name swapped",
    "delete_not_persisted": "deleting a contact in the app answers OK but keeps it",
    "resubscribe_ignored": "the preferences page confirms a resubscribe it never saved",
    "api_ignores_auth": "the public API answers without a Bearer token",
    "api_contact_tags_dropped": "the public API drops the tags of a contact it creates",
    "api_validation_reports_zero_cost": "the public API's validation response says it was free",
    "api_balance_stale": "the public API's credit balance ignores the journal",
    "api_endpoint_without_test": "a new documented endpoint ships with no test",
    "automation_ignores_unsubscribe": "an automation emails contacts who have unsubscribed",
}


def _load() -> frozenset:
    names = {n.strip() for n in os.getenv("DEMO_ESP_BUGS", "").split(",") if n.strip()}
    unknown = sorted(names - set(FLAGS))
    if unknown:
        raise SystemExit(f"DEMO_ESP_BUGS names unknown flag(s) {unknown}; "
                         f"known: {sorted(FLAGS)}")
    return frozenset(names)


ACTIVE = _load()


def active(name: str) -> bool:
    assert name in FLAGS, f"unknown bug flag {name!r}"
    return name in ACTIVE
