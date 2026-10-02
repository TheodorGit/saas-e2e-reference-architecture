"""Expectations that are True, False, or observed and recorded."""
from framework.reporting.recorder import StepRecorder

OBSERVE = None


def check(steps: StepRecorder, name: str, expected: bool | None, observed: bool,
          what: str, means: str = None, ui: bool = False, evidence: tuple = None) -> bool:
    observed = bool(observed)
    if expected is OBSERVE:
        return steps.step(name, lambda: observed,
                          expected=f"observed, not asserted: {what} = {observed}",
                          ui=ui, observed=observed)

    def verify():
        if evidence:
            steps.attach(*evidence)
        assert observed == expected, f"{what}: expected {expected}, observed {observed}"
        return observed
    return steps.step(name, verify, expected=f"{what} = {expected}", means=means, ui=ui)
