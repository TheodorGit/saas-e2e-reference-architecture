"""Demo ESP App configuration, read from the environment with safe demo defaults.

Nothing here is a secret: the demo login and API token exist so the stack runs
with no hand-filled .env. Never point this app at real people.
"""
import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    db_path: Path
    public_url: str            # base of every link placed in an email
    smtp_host: str
    smtp_port: int
    sender: str
    demo_email: str
    demo_password: str
    api_token: str
    credit_grant: int          # credits the demo account starts with
    validation_cost: int       # credits per billed address validation
    validation_free_window_s: int  # re-validating an address in this window is free
    ingest_delay_s: int        # stats and journal rows land this long after the event
    ui_latency_ms: int         # simulated server latency on read endpoints
    worker_tick_s: float
    inprocess_worker: bool     # run the worker inside the web process (local dev)


def load() -> Settings:
    return Settings(
        db_path=Path(os.getenv("DEMO_ESP_DB", "data/demo-esp.sqlite3")),
        public_url=os.getenv("DEMO_ESP_PUBLIC_URL", "http://localhost:8000").rstrip("/"),
        smtp_host=os.getenv("DEMO_ESP_SMTP_HOST", "localhost"),
        smtp_port=_int("DEMO_ESP_SMTP_PORT", 1025),
        sender=os.getenv("DEMO_ESP_SENDER", "Demo ESP App <news@demo-esp.test>"),
        demo_email=os.getenv("DEMO_ESP_DEMO_EMAIL", "demo@demo-esp.test"),
        demo_password=os.getenv("DEMO_ESP_DEMO_PASSWORD", "demo-esp-password"),
        api_token=os.getenv("DEMO_ESP_API_TOKEN", "demo-api-token"),
        credit_grant=_int("DEMO_ESP_CREDIT_GRANT", 100000),
        validation_cost=_int("DEMO_ESP_VALIDATION_COST", 5),
        validation_free_window_s=_int("DEMO_ESP_VALIDATION_FREE_WINDOW_S", 600),
        ingest_delay_s=_int("DEMO_ESP_INGEST_DELAY_S", 5),
        ui_latency_ms=_int("DEMO_ESP_UI_LATENCY_MS", 300),
        worker_tick_s=float(os.getenv("DEMO_ESP_WORKER_TICK_S", "1")),
        inprocess_worker=os.getenv("DEMO_ESP_INPROCESS_WORKER", "") == "1",
    )


SETTINGS = load()
