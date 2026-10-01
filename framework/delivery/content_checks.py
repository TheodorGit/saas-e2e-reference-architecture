"""What a delivered email must look like: the encoded standard.

These checks are the source of truth. A received email is asserted to MATCH
them; a mismatch is a finding about the email, never a reason to relax the check.

  - template variables rendered: no literal {{variable}} left, and the expected
    values present (a variable that renders to nothing leaves nothing behind, so
    only checking for leftovers would miss it)
  - special characters survive rendering
  - the unsubscribe standard: a footer link, and optionally a header line
  - RFC 8058 one-click: List-Unsubscribe (https + mailto) and List-Unsubscribe-Post
"""
import html as _html
import re
from dataclasses import dataclass

from framework.delivery.links import anchors

DEFAULT_TOKEN = r"\{\{\s*[\w.]+\s*\}\}"
ONE_CLICK_POST_VALUE = "List-Unsubscribe=One-Click"


def visible_text(html_body: str) -> str:
    """Approximate reader-visible text: no script/style, no tags, entities decoded."""
    if not html_body:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html_body)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def literal_tokens(*chunks, pattern: str = DEFAULT_TOKEN) -> list[str]:
    return sorted({m for c in chunks if c for m in re.findall(pattern, c)})


def assert_rendered(subject: str, html_body: str, expected: dict,
                    in_subject=(), in_body=(), token_pattern: str = DEFAULT_TOKEN) -> str:
    """Every key in in_subject/in_body renders its expected value, and no template
    variable is left literal anywhere."""
    subject = subject or ""
    body = visible_text(html_body)
    for where, keys, text in (("subject", in_subject, subject), ("body", in_body, body)):
        for key in keys:
            value = (expected.get(key) or "").strip()
            assert value, f"expected[{key!r}] is empty; nothing to check in the {where}"
            assert value in text, (
                f"Template variable {key!r} did not render in the {where}: expected "
                f"to find {value!r}")
    left = literal_tokens(subject, html_body, pattern=token_pattern)
    assert not left, f"Unrendered template variable(s) reached the inbox: {', '.join(left)}"
    shown = sorted(set(in_subject) | set(in_body))
    return f"rendered {', '.join(shown) or 'no named values'}; no literal variable left"


def assert_chars_survive(html_body: str, chars: str = "',%$#&") -> str:
    text = visible_text(html_body)
    missing = [c for c in chars if c not in text]
    assert not missing, f"Special character(s) {missing} did not survive rendering"
    return f"special characters {list(chars)} all rendered"


@dataclass(frozen=True)
class UnsubscribeStandard:
    footer_anchor_texts: tuple   # any one of these must be a link in the body
    header_phrase: str = ""      # if set, this line must appear, followed by a link


def assert_unsubscribe(html_body: str, standard: UnsubscribeStandard) -> str:
    html_body = html_body or ""
    if standard.header_phrase:
        assert standard.header_phrase in visible_text(html_body), (
            f"Unsubscribe header line missing: expected {standard.header_phrase!r}")
        assert re.search(re.escape(standard.header_phrase) + r"[\s\S]{0,200}?<a\b",
                         html_body), "Unsubscribe header line carries no link"
    labels = {label for _, label in anchors(html_body)}
    found = [t for t in standard.footer_anchor_texts if t in labels]
    assert found, (
        f"Unsubscribe footer link missing: no anchor reading any of "
        f"{list(standard.footer_anchor_texts)}")
    return f"unsubscribe footer link {found[0]!r}" + (
        "; header line present" if standard.header_phrase else "")


def list_unsubscribe_targets(headers: dict) -> list[str]:
    """The <...> entries of List-Unsubscribe, in order; [] when absent. Reads only:
    for flows that need the URL but are not the test of the header standard."""
    by_name = {k.lower(): v for k, v in (headers or {}).items()}
    return re.findall(r"<([^>]+)>", by_name.get("list-unsubscribe", ""))


def one_click_url(headers: dict, *, allowed_schemes=("https",)) -> str:
    """Assert the RFC 8058 headers and return the web URL a client POSTs to.

    RFC 8058 requires https, so that is the default. `allowed_schemes` is the
    seam for a local stack served over plain http: a suite widens it explicitly,
    and should say so in its report, rather than skipping the check.
    """
    by_name = {k.lower(): v for k, v in (headers or {}).items()}
    value = by_name.get("list-unsubscribe", "")
    assert value, "List-Unsubscribe header missing"
    entries = list_unsubscribe_targets(headers)
    prefixes = tuple(f"{s.lower()}://" for s in allowed_schemes)
    web = [e for e in entries if e.lower().startswith(prefixes)]
    shown = " or ".join(f"<{s}://...>" for s in allowed_schemes)
    assert web, f"List-Unsubscribe carries no {shown} entry: {value!r}"
    assert any(e.lower().startswith("mailto:") for e in entries), (
        f"List-Unsubscribe carries no <mailto:...> entry: {value!r}")
    post = by_name.get("list-unsubscribe-post", "").strip()
    assert post == ONE_CLICK_POST_VALUE, (
        f"List-Unsubscribe-Post is {post!r}, expected {ONE_CLICK_POST_VALUE!r}; "
        f"without it mail clients do not offer one-click")
    return web[0]
