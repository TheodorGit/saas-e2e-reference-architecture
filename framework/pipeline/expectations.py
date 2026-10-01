"""Three-valued expectations: true, false, or observe-and-record.

Some behaviours have a required answer (an unsubscribe must never count as
engagement: False). Some are product policy the run has no right to assert (does
a one-click unsubscribe also count as an open?). Forcing those into true/false makes
a test that breaks on a policy change, or one that asserts whatever happened
once. The third value, OBSERVE, records what the system did - visibly, in the
report - without passing judgement. Promoting it to True or False later is a
one-word change.
"""
from framework.reporting.recorder import StepRecorder

OBSERVE = None


def check(steps: StepRecorder, name: str, expected: bool | None, observed: bool,
          what: str, means: str = None, ui: bool = False, evidence: tuple = None) -> bool:
    """Assert `observed == expected`, or record it when expected is OBSERVE.
    Returns the observed value. ui=True marks a check of what is on screen;
    evidence=(label, content, ext) is what the check saw, kept if it fails."""
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
