"""Address validation through the public API is billed, and says so."""
import pytest

from example.suite import ledger_kinds as kinds

pytestmark = pytest.mark.api

VALIDATION_COST = 5  # the product's price for one billed validation


def test_api_validation_is_billed(v1, config, entity_name, record):
    token = entity_name("apivalidate")
    email = config.address(token)
    answer = v1.call("POST", "/v1/validate", json={"email": email})
    if answer is None or answer.status_code != 200:
        return  # the failed call is recorded; teardown fails the test
    body = answer.json()
    # A fresh, run-unique address: no free window can be open for it.
    record("validation", kinds.VALIDATION, cost=VALIDATION_COST, name=token, token=token,
           email=email, reference=body["reference"], expected_free=False)
    v1.check("the response states the charge", lambda: _charged(body),
             expected=f"cost {VALIDATION_COST}, not free",
             means="The API tells the client a billed action was free.")
    v1.check("the verdict is given", lambda: body["result"] in
             ("valid", "risky", "invalid") or _fail(f"verdict {body['result']!r}"),
             expected="valid, risky or invalid")
    v1.call("POST", "/v1/validate", expect=400, name="a malformed address is refused",
            json={"email": "not-an-address"})


def _charged(body: dict):
    assert body["cost"] == VALIDATION_COST and body["free"] is False, (
        f"response says cost {body['cost']}, free {body['free']}")


def _fail(message: str):
    raise AssertionError(message)
