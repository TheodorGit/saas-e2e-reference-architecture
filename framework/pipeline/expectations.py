"""Expectations that are True, False, or observed and recorded."""
from framework.reporting.recorder import CheckRecorder

OBSERVE = None


def check(checks: CheckRecorder, name: str, expected: bool | None, observed: bool,
          what: str, means: str | None = None, ui: bool = False,
          evidence: tuple | None = None) -> bool:
    observed = bool(observed)
    if expected is OBSERVE:
        return checks.check(name, lambda: observed,
                            expected=f"observed, not asserted: {what} = {observed}",
                            ui=ui, observed=observed)

    def verify():
        if evidence:
            checks.attach(*evidence)
        assert observed == expected, f"{what}: expected {expected}, observed {observed}"
        return observed
    return checks.check(name, verify, expected=f"{what} = {expected}", means=means, ui=ui)
