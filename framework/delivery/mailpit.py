"""MailClient for Mailpit, the local SMTP sink the example runs against."""
from datetime import datetime

import requests

from framework.delivery.mail_client import MailClient, Message

SEARCH_LIMIT = 200


def _quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


class MailpitClient(MailClient):
    def __init__(self, base_url: str, timeout: float = 15):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.http = requests.Session()

    def _get(self, path: str, **params) -> dict:
        response = self.http.get(f"{self.base}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def search(self, subject: str = None, to: str = None) -> list[Message]:
        terms = []
        if subject:
            terms.append(f"subject:{_quote(subject)}")
        if to:
            terms.append(f"to:{_quote(to)}")
        if terms:
            data = self._get("/api/v1/search", query=" ".join(terms), limit=SEARCH_LIMIT)
        else:
            data = self._get("/api/v1/messages", limit=SEARCH_LIMIT)
        messages = [self._message(m) for m in data.get("messages") or []]
        # The server search is tokenised; the contract here is a substring match.
        if subject:
            messages = [m for m in messages if subject.lower() in m.subject.lower()]
        if to:
            messages = [m for m in messages if to.lower() in (a.lower() for a in m.to)]
        return messages

    def html(self, message_id: str) -> str:
        return self._get(f"/api/v1/message/{message_id}").get("HTML") or ""

    def headers(self, message_id: str) -> dict[str, str]:
        raw = self._get(f"/api/v1/message/{message_id}/headers")
        return {name: (values[0] if isinstance(values, list) and values else values)
                for name, values in raw.items()}

    def raw(self, message_id: str) -> bytes:
        response = self.http.get(f"{self.base}/api/v1/message/{message_id}/raw",
                                 timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def delete(self, message_ids: list[str]) -> int:
        if not message_ids:
            return 0
        response = self.http.delete(f"{self.base}/api/v1/messages",
                                    json={"IDs": list(message_ids)}, timeout=self.timeout)
        response.raise_for_status()
        return len(message_ids)

    @staticmethod
    def _message(raw: dict) -> Message:
        created = raw.get("Created")
        try:
            received = datetime.fromisoformat(created.replace("Z", "+00:00")) \
                if created else None
        except ValueError:
            received = None
        return Message(
            id=raw["ID"],
            subject=raw.get("Subject") or "",
            to=tuple((a.get("Address") or "").lower() for a in raw.get("To") or []),
            sender=((raw.get("From") or {}).get("Address") or "").lower(),
            received_at=received,
            extra={"raw": raw},
        )
