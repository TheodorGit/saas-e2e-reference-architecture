import pytest

from framework.delivery import links
from framework.delivery.content_checks import (
    UnsubscribeStandard,
    assert_chars_survive,
    assert_rendered,
    assert_unsubscribe,
    one_click_url,
    visible_text,
)
from framework.delivery.mail_client import MailClient, Message

pytestmark = pytest.mark.unit

PATTERNS = links.TrackerPatterns(open_pixel=r"/t/open/", click=r"/t/click/")

BODY = """
<p>No longer interested? You can <a href="https://t.example.com/t/click/u1">leave here</a>.</p>
<p>Hello Ada, your address is ada+1@example.com. Chars: ' , % $ # &amp;</p>
<p><a href="https://t.example.com/t/click/c9">QA click target</a></p>
<p><a href="https://t.example.com/t/click/u2">Unsubscribe</a></p>
<img src="https://t.example.com/t/open/p1" width="1">
"""
STANDARD = UnsubscribeStandard(footer_anchor_texts=("Unsubscribe",),
                               header_phrase="No longer interested?")


class FakeInbox(MailClient):
    def __init__(self, messages, bodies=None, arrive_after=0):
        self.messages, self.bodies = messages, bodies or {}
        self.deleted, self.calls, self.arrive_after = [], 0, arrive_after

    def search(self, subject=None, to=None):
        self.calls += 1
        if self.calls <= self.arrive_after:
            return []
        return [m for m in self.messages
                if (subject is None or subject in m.subject)
                and (to is None or to in m.to) and m.id not in self.deleted]

    def html(self, message_id):
        return self.bodies.get(message_id, "")

    def headers(self, message_id):
        return {}

    def raw(self, message_id):
        return b""

    def delete(self, message_ids):
        self.deleted += list(message_ids)
        return len(message_ids)


def test_rendered_values_and_no_leftover_tokens():
    expected = {"first": "Ada", "email": "ada+1@example.com"}
    summary = assert_rendered("Hi Ada - QA-tok", BODY, expected,
                              in_subject=["first"], in_body=["email"])
    assert "no literal variable" in summary


def test_a_literal_token_is_a_defect():
    with pytest.raises(AssertionError, match="Unrendered"):
        assert_rendered("Hi {{first_name}}", "<p>x</p>", {})


def test_a_blank_substitution_is_caught_by_the_expected_value():
    with pytest.raises(AssertionError, match="did not render"):
        assert_rendered("Hi , welcome", "<p>x</p>", {"first": "Ada"}, in_subject=["first"])


def test_entities_are_decoded_before_checking_characters():
    assert "&" in visible_text(BODY)
    assert_chars_survive(BODY)
    with pytest.raises(AssertionError):
        assert_chars_survive("<p>plain</p>")


def test_unsubscribe_standard_needs_footer_and_header():
    assert_unsubscribe(BODY, STANDARD)
    with pytest.raises(AssertionError, match="footer"):
        assert_unsubscribe(BODY.replace(">Unsubscribe<", ">Bye<"), STANDARD)
    with pytest.raises(AssertionError, match="header"):
        assert_unsubscribe(BODY.replace("No longer interested?", ""), STANDARD)


ONE_CLICK = {"List-Unsubscribe": "<https://app.example.com/u/1>, <mailto:u@example.com>",
             "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def test_one_click_returns_the_https_url_case_insensitively():
    assert one_click_url(ONE_CLICK) == "https://app.example.com/u/1"
    assert one_click_url({k.lower(): v for k, v in ONE_CLICK.items()}).startswith("https")


@pytest.mark.parametrize("change, match", [
    ({"List-Unsubscribe": ""}, "missing"),
    ({"List-Unsubscribe-Post": ""}, "List-Unsubscribe-Post"),
    ({"List-Unsubscribe": "<https://app.example.com/u/1>"}, "mailto"),
    ({"List-Unsubscribe": "<mailto:u@example.com>"}, "https"),
])
def test_one_click_defects(change, match):
    with pytest.raises(AssertionError, match=match):
        one_click_url({**ONE_CLICK, **change})


def test_one_click_http_is_refused_unless_the_suite_widens_the_schemes():
    local = {**ONE_CLICK, "List-Unsubscribe": "<http://app:8000/u/1>, <mailto:u@example.com>"}
    with pytest.raises(AssertionError, match="https"):
        one_click_url(local)
    widened = one_click_url(local, allowed_schemes=("https", "http"))
    assert widened == "http://app:8000/u/1"
    assert one_click_url(ONE_CLICK, allowed_schemes=("https", "http")).startswith("https")


def test_links_are_found_by_what_the_reader_sees():
    assert links.find_open_pixel(BODY, PATTERNS).endswith("/p1")
    assert links.find_link(BODY, "click target").endswith("/c9")
    assert links.find_unsubscribe_link(BODY).endswith("/u2")
    assert links.find_unsubscribe_link(BODY.replace(">Unsubscribe<", ">Bye<"),
                                       context_phrases=("No longer interested",)).endswith("/u1")


def test_engagement_is_itemised_and_failures_are_never_counted(monkeypatch):
    fired = []
    monkeypatch.setattr(links, "fire", lambda url, timeout=15: fired.append(url) or {
        "url": url, "status": 200 if "p1" in url else 500, "ok": "p1" in url, "reason": ""})
    inbox = FakeInbox([], bodies={"m1": BODY, "m2": "<p>no tracking</p>"})
    copies = {"a@example.com": Message("m1", "s"), "b@example.com": Message("m2", "s")}
    result = links.engage(inbox, copies, PATTERNS, click_text="click target")
    assert result["opened"] == ["a@example.com"]
    assert result["clicked"] == []
    assert any("answered 500" in f for f in result["failures"])
    assert any(f.startswith("b@example.com: open") for f in result["failures"])


def test_wait_for_polls_until_the_mail_arrives(monkeypatch):
    monkeypatch.setattr("framework.polling.time.sleep", lambda s: None)
    inbox = FakeInbox([Message("m1", "QA-tok hello", ("a@example.com",))], arrive_after=2)
    found = inbox.wait_for(subject="QA-tok", timeout_s=60, poll_s=1)
    assert found.id == "m1" and inbox.calls == 3


def test_wait_for_each_names_who_is_missing(monkeypatch):
    monkeypatch.setattr("framework.polling.time.sleep", lambda s: None)
    inbox = FakeInbox([Message("m1", "QA-tok", ("a@example.com",))])
    copies = inbox.wait_for_each("QA-tok", ["a@example.com", "b@example.com"],
                                 timeout_s=0, poll_s=1)
    assert set(copies) == {"a@example.com"}


def test_delete_matching_bins_only_the_runs_mail():
    inbox = FakeInbox([Message("m1", "QA-tok a"), Message("m2", "other")])
    assert inbox.delete_matching(subject="QA-tok") == 1 and inbox.deleted == ["m1"]
