"""Multi-step flows several tests share."""
from example.suite.app_client import AppApi
from framework.polling import poll_until


def wait_until_sent(api: AppApi, batch_id: int, budget_s: float) -> dict:
    batch, waited = poll_until(lambda: api.batch(batch_id),
                               lambda b: b["status"] in ("sent", "failed"), budget_s, 1)
    assert batch["status"] == "sent", (
        f"email batch {batch_id} is {batch['status']!r} after {waited:.0f}s")
    return batch


def body_with_link(public_url: str, greeting: str = "Hello {{first_name}},") -> str:
    return (f"<p>{greeting}</p><p>This month in the demo: nothing real.</p>"
            f'<p><a href="{public_url}/landing">Read more</a></p>')
