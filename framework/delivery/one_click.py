"""RFC 8058 one-click unsubscribe, sent the way a mail client sends it."""
import requests

from framework.delivery.content_checks import ONE_CLICK_POST_VALUE


def post_one_click(url: str, timeout: float = 30) -> dict:
    key, value = ONE_CLICK_POST_VALUE.split("=", 1)
    response = requests.post(url, data={key: value}, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:300]}
    if not isinstance(body, dict):
        body = {"body": body}
    return {"status_code": response.status_code, **body}
