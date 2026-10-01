"""Docs coverage: every endpoint the API documents was executed this session."""
import pytest

from framework.api.coverage import assert_exercised

pytestmark = pytest.mark.api


def test_documented_endpoints_were_exercised(v1, api_coverage):
    index = v1.call("GET", "/v1/")
    if index is None or index.status_code != 200:
        return  # the failed call is recorded; teardown fails the test
    documented = [(e["method"], e["path"]) for e in index.json()["endpoints"]]

    def covered():
        lines = (["documented:"] + [f"  {m} {p}" for m, p in documented]
                 + ["executed this session:"]
                 + [f"  {k}" for k in sorted(api_coverage.executed())])
        v1.steps.attach("documented and executed endpoints", "\n".join(lines))
        return assert_exercised(documented, api_coverage)
    v1.check("every documented endpoint was executed this session", covered,
             expected=f"all {len(documented)} documented endpoints called by some test",
             means="The API documents an endpoint no test exercises.")
