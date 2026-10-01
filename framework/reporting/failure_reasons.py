"""Plain-language failure reasons for the report.

A reason states ONLY what the failure proves. The test knows what it observed and
how long it waited; it does not know why. No causes, no "probably", no "either X
or Y": a guess in a status report is worse than no sentence at all, so an
unrecognised exception gets no sentence and the raw error speaks for itself.

Used when a step did not author its own `means=`.
"""

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
    """A factual sentence for an exception, or '' when none can be said."""
    return _for(type(exc).__name__, str(exc).strip())


def classify_failure_text(failure: str) -> str:
    """The same, for a failure that happened outside any step, where only
    pytest's text is left. pytest prefixes error lines with 'E'."""
    for line in (failure or "").splitlines():
        line = line.strip()
        if line.startswith("E "):
            name, _, rest = line[2:].strip().partition(":")
            return _for(name.strip(), rest.strip())
    return ""


def first_error_line(failure: str) -> str:
    """One readable line from pytest's failure text."""
    lines = [ln.rstrip() for ln in (failure or "").splitlines() if ln.strip()]
    errors = [ln.strip()[2:].strip() for ln in lines if ln.strip().startswith("E ")]
    if errors:
        return errors[0][:300]
    return lines[-1][:300] if lines else ""
