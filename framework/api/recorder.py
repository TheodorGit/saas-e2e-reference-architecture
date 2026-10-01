"""API calls as recorded steps, finished and asserted in teardown.

Each call is a step that declares what it expects (method, route, status) and
records what came back. Checks on the response are steps too. All of them are
soft: one wrong answer does not hide the independent checks after it.

The danger of soft checks is a test that ends without raising them - it passes
while holding a failure. So raising is not left to the test: the fixture that
hands out recorders raises every held failure in teardown, and a test that
passed its body still fails. A test can never pass while holding a failed step.

Every call is also counted against its route TEMPLATE ("/items/{item_id}"),
not the concrete URL, so docs coverage can be checked (see coverage.py).
"""
from collections.abc import Callable
from dataclasses import dataclass

import requests

from framework.reporting.recorder import StepRecorder

BODY_SHOWN = 200
TIMEOUT = 30


@dataclass(frozen=True)
class Call:
    method: str
    template: str
    url: str
    status: int | None
    expected: int
    nodeid: str


class Coverage:
    """Every call made this session, keyed by method and route template."""

    def __init__(self):
        self.calls: list[Call] = []

    def add(self, call: Call):
        self.calls.append(call)

    def executed(self) -> set[str]:
        return {f"{c.method} {c.template}" for c in self.calls if c.status is not None}


class ApiRecorder:
    def __init__(self, http: requests.Session, base_url: str, steps: StepRecorder,
                 coverage: Coverage, nodeid: str, label: str = ""):
        self.http = http
        self.base = base_url.rstrip("/")
        self.steps = steps
        self.coverage = coverage
        self.nodeid = nodeid
        self.label = label
        self.last = None

    def call(self, method: str, template: str, expect: int = 200, name: str = None,
             params: dict = None, json=None, **path) -> requests.Response | None:
        """Call `template` filled with `path`; record the step and the coverage.
        Returns the response, or None when the request itself failed."""
        method = method.upper()
        url = self.base + template.format(**path)
        step = name or f"{self.label}{method} {template}"
        try:
            response = self.http.request(method, url, params=params, json=json,
                                         timeout=TIMEOUT)
        except requests.RequestException as exc:
            self.coverage.add(Call(method, template, url, None, expect, self.nodeid))
            self.steps.soft_step(step, lambda error=exc: _raise(error),
                                 expected=f"{method} {template} answers {expect}")
            return None
        self.coverage.add(Call(method, template, url, response.status_code, expect,
                               self.nodeid))
        self.last = response

        def verify():
            # The exchange is this check's evidence; kept only if it fails.
            self.steps.attach("request and response", exchange(response))
            assert response.status_code == expect, (
                f"{method} {url} answered {response.status_code}, expected {expect}: "
                f"{response.text[:BODY_SHOWN]}")
            return response.status_code
        self.steps.soft_step(step, verify, expected=f"{method} {template} answers {expect}")
        return response

    def check(self, name: str, fn: Callable, expected: str, means: str = None):
        """A soft check on what came back; the last exchange is its evidence."""
        def checked():
            if self.last is not None:
                self.steps.attach("the response it checked", exchange(self.last))
            return fn()
        return self.steps.soft_step(name, checked, expected=expected, means=means)


def exchange(response) -> str:
    """A request and its response as text: what an API check saw."""
    request = getattr(response, "request", None)
    lines = [f"{getattr(request, 'method', '')} {getattr(request, 'url', '')}".strip()]
    body = getattr(request, "body", None)
    if body:
        lines += ["", body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)]
    lines += ["", f"HTTP {response.status_code}"]
    headers = getattr(response, "headers", None) or {}
    lines += [f"{k}: {v}" for k, v in headers.items()]
    lines += ["", getattr(response, "text", "")]
    return "\n".join(lines)


def _raise(exc: BaseException):
    raise exc
