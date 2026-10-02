"""The MailClient protocol and the helpers built on it."""
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
        ...

    @abstractmethod
    def html(self, message_id: str) -> str:
        ...

    @abstractmethod
    def headers(self, message_id: str) -> dict[str, str]:
        ...

    @abstractmethod
    def raw(self, message_id: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, message_ids: list[str]) -> int:
        ...

    def wait_for(self, subject: str = None, to: str = None, timeout_s: float = 300,
                 poll_s: float = 5, exclude: tuple = ()) -> Message | None:
        def fresh():
            return [m for m in self.search(subject=subject, to=to) if m.id not in exclude]

        found, _ = poll_until(fresh, bool, timeout_s, poll_s)
        return found[0] if found else None

    def wait_for_each(self, subject: str, recipients, timeout_s: float = 300,
                      poll_s: float = 5) -> dict[str, Message]:
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
        return self.delete([m.id for m in self.search(subject=subject, to=to)])
