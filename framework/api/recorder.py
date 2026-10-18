"""API calls and their verifications, recorded as soft checks."""
import os
from collections.abc import Callable
from dataclasses import dataclass

import requests

from framework.reporting.recorder import CheckRecorder

BODY_SHOWN = 200
TIMEOUT = int(os.getenv("E2E_HTTP_TIMEOUT_S", "30"))


@dataclass(frozen=True)
class Call:
    method: str
    template: str
    url: str
    status: int | None
    expected: int
    nodeid: str


class Coverage:
    def __init__(self):
        self.calls: list[Call] = []

    def add(self, call: Call):
        self.calls.append(call)

    def executed(self) -> set[str]:
        return {f"{c.method} {c.template}" for c in self.calls if c.status is not None}


class ApiRecorder:
    def __init__(self, http: requests.Session, base_url: str, checks: CheckRecorder,
                 coverage: Coverage, nodeid: str, label: str = ""):
        self.http = http
        self.base = base_url.rstrip("/")
        self.checks = checks
        self.coverage = coverage
        self.nodeid = nodeid
        self.label = label
        self.last = None

    def call(self, method: str, template: str, expect: int = 200, name: str | None = None,
             params: dict | None = None, json=None, **path) -> requests.Response | None:
        method = method.upper()
        url = self.base + template.format(**path)
        check = name or f"{self.label}{method} {template}"
        try:
            response = self.http.request(method, url, params=params, json=json,
                                         timeout=TIMEOUT)
        except requests.RequestException as exc:
            self.coverage.add(Call(method, template, url, None, expect, self.nodeid))
            self.checks.soft_check(check, lambda error=exc: _raise(error),
                                   expected=f"{method} {template} answers {expect}")
            return None
        self.coverage.add(Call(method, template, url, response.status_code, expect,
                               self.nodeid))
        self.last = response

        def verify():
            self.checks.attach("request and response", exchange(response))
            assert response.status_code == expect, (
                f"{method} {url} answered {response.status_code}, expected {expect}: "
                f"{response.text[:BODY_SHOWN]}")
            return response.status_code
        self.checks.soft_check(check, verify, expected=f"{method} {template} answers {expect}")
        return response

    def check(self, name: str, fn: Callable, expected: str, means: str | None = None):
        subject = self.last

        def checked():
            if subject is not None:
                self.checks.attach("the response it checked", exchange(subject))
            return fn()
        return self.checks.soft_check(name, checked, expected=expected, means=means)


def exchange(response) -> str:
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
