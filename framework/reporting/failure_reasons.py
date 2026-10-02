"""Plain-language failure reasons for the report."""

# Playwright's expect() raises a plain AssertionError with these prefixes.
_EXPECT_PREFIXES = ("Locator expected", "Page expected", "APIResponse expected")

_BY_TYPE = {
    "TimeoutError": "What this step waited for never appeared within the timeout.",
    "ValueError": "The system returned data this step could not read.",
    "KeyError": "The system returned data this step could not read.",
    "AttributeError": "The system returned data this step could not read.",
    "TypeError": "The system returned data this step could not read.",
    "IndexError": "The system returned data this step could not read.",
    "RuntimeError": "The run could not reach a usable state.",
}


def _for(name: str, text: str) -> str:
    if name == "AssertionError":
        if text.startswith(_EXPECT_PREFIXES):
            return "The page did not show what this step checked for."
        return "A value the system reported did not match what this run did."
    return _BY_TYPE.get(name, "")


def classify(exc: BaseException) -> str:
    return _for(type(exc).__name__, str(exc).strip())


def classify_failure_text(failure: str) -> str:
    for line in (failure or "").splitlines():
        line = line.strip()
        if line.startswith("E "):
            name, _, rest = line[2:].strip().partition(":")
            return _for(name.strip(), rest.strip())
    return ""


def first_error_line(failure: str) -> str:
    lines = [ln.rstrip() for ln in (failure or "").splitlines() if ln.strip()]
    errors = [ln.strip()[2:].strip() for ln in lines if ln.strip().startswith("E ")]
    if errors:
        return errors[0][:300]
    return lines[-1][:300] if lines else ""
