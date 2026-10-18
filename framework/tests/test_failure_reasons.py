"""Plain-language reasons: dotted exception names, mapped types, and the first error line."""
import pytest

from framework.reporting.failure_reasons import (
    classify,
    classify_failure_text,
    first_error_line,
)

pytestmark = pytest.mark.unit

TIMEOUT_FAILURE = """
self = <Page url='http://localhost:8000/#/contacts'>
E   playwright._impl._errors.TimeoutError: Timeout 15000ms exceeded.
"""


def test_a_dotted_exception_name_classifies():
    assert classify_failure_text(TIMEOUT_FAILURE) == (
        "What this check waited for never appeared within the timeout.")


@pytest.mark.parametrize("name", ["TimeoutError", "playwright._impl._errors.TimeoutError"])
def test_dotted_and_bare_names_read_the_same(name):
    assert classify_failure_text(f"E   {name}: Timeout 15000ms exceeded.").startswith(
        "What this check waited for")


@pytest.mark.parametrize("name, reason", [
    ("ValidationError", "The response did not match the documented contract."),
    ("ConnectError", "The system under test could not be reached."),
    ("ConnectTimeout", "The system under test could not be reached."),
    ("ReadTimeout", "The system under test did not answer in time."),
    ("HTTPStatusError", "The API answered with a status this check does not accept."),
    ("JSONDecodeError", "The API answered with something that is not JSON."),
])
def test_transport_and_contract_failures_have_a_reason(name, reason):
    assert classify_failure_text(f"E   requests.exceptions.{name}: nothing readable") == reason
    assert classify_failure_text(f"E   {name}: nothing readable") == reason


def test_an_unmapped_name_stays_blank():
    assert classify_failure_text("E   some.pkg.NeverSeenError: who knows") == ""
    assert classify_failure_text("") == ""


def test_an_assertion_keeps_its_own_words_and_loses_its_class_name():
    assert first_error_line("E   AssertionError: audience differ: missing ['a@x.io']") == (
        "audience differ: missing ['a@x.io']")


def test_other_classes_keep_the_name_that_is_the_story():
    assert first_error_line("E   KeyError: 'opened_by'") == "KeyError: 'opened_by'"


def test_classify_reads_a_live_exception():
    assert classify(TimeoutError("waited")) == (
        "What this check waited for never appeared within the timeout.")
    assert classify(KeyError("opened_by")) == "The system returned data this check could not read."
