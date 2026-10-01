"""The inbox, as the suite sees it.

Delivery is proven where a recipient would look: in an inbox the run can read.
Adapters implement five primitives (search, html, headers, raw, delete); waiting
and per-recipient collection are built once, here, on top of them. `raw` is the
message exactly as delivered - the evidence a failed inbox check keeps.

Searches are by the run's unique subject token, so they can only find this run's
mail. Where the subject is fixed content that exists from earlier runs, the
recipient (a run-unique alias) is what makes the match unambiguous.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from framework.polling import poll_until


@dataclass(frozen=True)
class Message:
    id: str
    subject: str
    to: tuple[str, ...] = ()
    sender: str = ""
    received_at: datetime = None
    extra: dict = field(default_factory=dict, compare=False, hash=False)


class MailClient(ABC):
    @abstractmethod
    def search(self, subject: str = None, to: str = None) -> list[Message]:
        """Messages whose subject CONTAINS `subject` and addressed to `to`."""

    @abstractmethod
    def html(self, message_id: str) -> str:
        """The message's HTML body ('' when it has none)."""

    @abstractmethod
    def headers(self, message_id: str) -> dict[str, str]:
        """Top-level headers, first value per name."""

    @abstractmethod
    def raw(self, message_id: str) -> bytes:
        """The whole message as delivered (RFC 5322 source), for evidence."""

    @abstractmethod
    def delete(self, message_ids: list[str]) -> int:
        """Remove messages; returns how many were removed."""

    # --- built on the primitives --------------------------------------------

    def wait_for(self, subject: str = None, to: str = None, timeout_s: float = 300,
                 poll_s: float = 5, exclude: tuple = ()) -> Message | None:
        """The first matching message not in `exclude`, or None after the budget."""
        def fresh():
            return [m for m in self.search(subject=subject, to=to) if m.id not in exclude]

        found, _ = poll_until(fresh, bool, timeout_s, poll_s)
        return found[0] if found else None

    def wait_for_each(self, subject: str, recipients, timeout_s: float = 300,
                      poll_s: float = 5) -> dict[str, Message]:
        """Each recipient's OWN copy: {address: message}. Missing recipients are
        absent from the result, so the caller can name them."""
        wanted = {r.lower() for r in recipients}

        def collect():
            copies = {}
            for message in self.search(subject=subject):
                for address in message.to:
                    if address.lower() in wanted and address.lower() not in copies:
                        copies[address.lower()] = message
            return copies

        copies, _ = poll_until(collect, lambda c: set(c) >= wanted, timeout_s, poll_s)
        return copies

    def delete_matching(self, subject: str = None, to: str = None) -> int:
        """Bin a run's own mail, matched by its token or run-unique recipient."""
        return self.delete([m.id for m in self.search(subject=subject, to=to)])
