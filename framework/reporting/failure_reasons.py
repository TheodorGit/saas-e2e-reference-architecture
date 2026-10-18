"""Plain-language failure reasons for the report."""

# Playwright's expect() raises a plain AssertionError with these prefixes.
_EXPECT_PREFIXES = ("Locator expected", "Page expected", "APIResponse expected")
_ASSERTION = "AssertionError:"
_LINE_MAX = 300

_BY_TYPE = {
    "TimeoutError": "What this check waited for never appeared within the timeout.",
    "ValueError": "The system returned data this check could not read.",
    "KeyError": "The system returned data this check could not read.",
    "AttributeError": "The system returned data this check could not read.",
    "TypeError": "The system returned data this check could not read.",
    "IndexError": "The system returned data this check could not read.",
    "ValidationError": "The response did not match the documented contract.",
    "ConnectError": "The system under test could not be reached.",
    "ConnectTimeout": "The system under test could not be reached.",
    "ReadTimeout": "The system under test did not answer in time.",
    "HTTPStatusError": "The API answered with a status this check does not accept.",
    "JSONDecodeError": "The API answered with something that is not JSON.",
    "RuntimeError": "The run could not reach a usable state.",
}


def _for(name: str, text: str) -> str:
    if name == "AssertionError":
        if text.startswith(_EXPECT_PREFIXES):
            return "The page did not show what this check checked for."
        return "A value the system reported did not match what this run did."
    return _BY_TYPE.get(name, "")


def classify(exc: BaseException) -> str:
    return _for(type(exc).__name__, str(exc).strip())


def classify_failure_text(failure: str) -> str:
    for line in (failure or "").splitlines():
        line = line.strip()
        if line.startswith("E "):
            name, _, rest = line[2:].strip().partition(":")
            # Pytest prints the full dotted path, such as playwright._impl._errors.TimeoutError.
            return _for(name.strip().rsplit(".", 1)[-1], rest.strip())
    return ""


def first_error_line(failure: str) -> str:
    lines = [ln.rstrip() for ln in (failure or "").splitlines() if ln.strip()]
    errors = [ln.strip()[2:].strip() for ln in lines if ln.strip().startswith("E ")]
    line = errors[0] if errors else (lines[-1] if lines else "")
    # An assertion states its reason in its own words; other class names are the story.
    if line.startswith(_ASSERTION):
        line = line[len(_ASSERTION):].strip()
    return line[:_LINE_MAX]
