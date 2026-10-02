"""Demo ESP App configuration, read from the environment with safe demo defaults."""
import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    db_path: Path
    public_url: str
    smtp_host: str
    smtp_port: int
    sender: str
    demo_email: str
    demo_password: str
    api_token: str
    credit_grant: int
    validation_cost: int
    validation_free_window_s: int
    ingest_delay_s: int
    ui_latency_ms: int
    worker_tick_s: float
    inprocess_worker: bool


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
