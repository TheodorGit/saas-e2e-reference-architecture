"""Where the suite points, read from the environment with local-stack defaults."""
import os
from dataclasses import dataclass

from framework.safety.guards import same_inbox


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class SuiteConfig:
    base_url: str
    mailpit_url: str
    email: str
    password: str
    api_token: str
    inbox: str
    audience_cap: int
    mail_budget_s: int
    ingest_budget_s: int
    max_window_wait_s: int

    def address(self, token: str) -> str:
        local, _, domain = self.inbox.partition("@")
        return f"{local}+{token.lower()}@{domain}"

    def is_ours(self, address: str, run_id: str) -> bool:
        return same_inbox(address, self.inbox) and run_id.lower() in address.lower()

    @property
    def one_click_schemes(self) -> tuple:
        # RFC 8058 wants https; a local stack over plain http is widened, visibly.
        return ("https",) if self.base_url.startswith("https://") else ("https", "http")


def load() -> SuiteConfig:
    return SuiteConfig(
        base_url=os.getenv("DEMO_ESP_URL", "http://localhost:8000").rstrip("/"),
        mailpit_url=os.getenv("E2E_MAILPIT_URL", "http://localhost:8025").rstrip("/"),
        email=os.getenv("DEMO_ESP_EMAIL", "demo@demo-esp.test"),
        password=os.getenv("DEMO_ESP_PASSWORD", "demo-esp-password"),
        api_token=os.getenv("DEMO_ESP_API_TOKEN", "demo-api-token"),
        inbox=os.getenv("E2E_INBOX", "qa@example.com"),
        audience_cap=_int("E2E_AUDIENCE_CAP", 10),
        mail_budget_s=_int("E2E_MAIL_BUDGET_S", 60),
        ingest_budget_s=_int("E2E_INGEST_BUDGET_S", 60),
        max_window_wait_s=_int("E2E_MAX_WINDOW_WAIT_S", 90),
    )
