"""The Demo ESP App's JSON surfaces, as the suite reads them."""
import requests

from framework.delivery.content_checks import UnsubscribeStandard
from framework.delivery.links import TrackerPatterns

TIMEOUT = 30

TRACKERS = TrackerPatterns(open_pixel=r"/t/o/[\w-]+\.gif$", click=r"/t/c/[\w-]+/\d+$")
UNSUBSCRIBE = UnsubscribeStandard(footer_anchor_texts=("Unsubscribe",),
                                  header_phrase="No longer want these emails?")


class AppError(RuntimeError):
    pass


class _Client:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.http = requests.Session()

    def call(self, method: str, path: str, **kwargs):
        response = self.http.request(method, f"{self.base}{path}", timeout=TIMEOUT, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise AppError(f"{method} {path} answered {response.status_code}: {detail}")
        return response.json() if "json" in response.headers.get("content-type", "") \
            else response.text


class AppApi(_Client):
    def __init__(self, base_url: str, email: str, password: str):
        super().__init__(base_url)
        self.call("POST", "/api/login", json={"email": email, "password": password})

    @property
    def session_cookie(self) -> str:
        return self.http.cookies.get("esp_session")

    def dashboard(self) -> dict:
        return self.call("GET", "/api/dashboard")

    def contacts(self, q: str = "", tag: str = "") -> list[dict]:
        return self.call("GET", "/api/contacts", params={"q": q, "tag": tag})["items"]

    def contact(self, email: str) -> dict | None:
        found = [c for c in self.contacts(q=email) if c["email"] == email.lower()]
        return found[0] if found else None

    def add_contact(self, email: str, first_name: str = "", last_name: str = "",
                    tags=(), status: str = "subscribed") -> dict:
        return self.call("POST", "/api/contacts", json={
            "email": email, "first_name": first_name, "last_name": last_name,
            "tags": list(tags), "status": status})

    def bulk_tag(self, contact_ids, tag: str) -> dict:
        return self.call("POST", "/api/contacts/bulk-tag",
                         json={"ids": list(contact_ids), "tag": tag, "action": "add"})

    def delete_contact(self, contact_id) -> dict:
        return self.call("DELETE", f"/api/contacts/{contact_id}")

    def create_suppression(self, name: str, emails) -> dict:
        return self.call("POST", "/api/address-suppression-lists",
                         json={"name": name, "emails": list(emails)})

    def delete_suppression(self, list_id) -> dict:
        return self.call("DELETE", f"/api/address-suppression-lists/{list_id}")

    def create_batch(self, name: str, subject: str, body_html: str,
                     audience_tag: str = None, suppression_list_ids=()) -> dict:
        return self.call("POST", "/api/email-batches", json={
            "name": name, "subject": subject, "body_html": body_html,
            "audience_tag": audience_tag, "suppression_list_ids": list(suppression_list_ids)})

    def credits(self) -> dict:
        return self.call("GET", "/api/credits")

    def batch(self, batch_id) -> dict:
        return self.call("GET", f"/api/email-batches/{batch_id}")

    def batch_named(self, name: str) -> dict | None:
        return next((b for b in self.call("GET", "/api/email-batches") if b["name"] == name),
                    None)

    def create_automation(self, name: str, trigger_tag: str, delay_s: int, subject: str,
                          body_html: str) -> dict:
        return self.call("POST", "/api/automations", json={
            "name": name, "trigger_tag": trigger_tag, "delay_s": delay_s,
            "subject": subject, "body_html": body_html})

    def automation(self, automation_id) -> dict:
        return self.call("GET", f"/api/automations/{automation_id}")

    def delete_automation(self, automation_id) -> dict:
        return self.call("DELETE", f"/api/automations/{automation_id}")


class PublicApi(_Client):
    def __init__(self, base_url: str, token: str):
        super().__init__(base_url)
        self.http.headers["Authorization"] = f"Bearer {token}"

    def report(self, batch_id) -> dict:
        return self.call("GET", f"/v1/email-batches/{batch_id}/report")

    def credits(self) -> dict:
        return self.call("GET", "/v1/credits")

    def journal_since(self, after_id: int) -> list[dict]:
        return [row for row in self.credits()["journal"] if row["id"] > after_id]
