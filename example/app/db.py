"""SQLite storage shared by the web process and the worker."""
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from example.app.settings import SETTINGS

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL DEFAULT '', last_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'subscribed', created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS contact_tags (
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    tag TEXT NOT NULL, PRIMARY KEY (contact_id, tag));

CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY, email TEXT NOT NULL, result TEXT NOT NULL,
    cost INTEGER NOT NULL, validated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS suppression_lists (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS suppression_entries (
    list_id INTEGER NOT NULL REFERENCES suppression_lists(id) ON DELETE CASCADE,
    email TEXT NOT NULL, PRIMARY KEY (list_id, email));

CREATE TABLE IF NOT EXISTS email_batches (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, subject TEXT NOT NULL,
    body_html TEXT NOT NULL, audience_tag TEXT,
    suppression_list_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL, scheduled_at TEXT, sent_at TEXT,
    recipients INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS email_batch_links (
    batch_id INTEGER NOT NULL REFERENCES email_batches(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL, url TEXT NOT NULL, PRIMARY KEY (batch_id, idx));

-- An automation: adding its trigger tag to a contact starts a run, and the run's
-- email goes out once the delay is up.
CREATE TABLE IF NOT EXISTS automations (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, trigger_tag TEXT NOT NULL,
    delay_s INTEGER NOT NULL, subject TEXT NOT NULL, body_html TEXT NOT NULL,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL, email TEXT NOT NULL, status TEXT NOT NULL,
    reason TEXT, enrolled_at TEXT NOT NULL, due_at TEXT NOT NULL, sent_at TEXT);

-- One row per email sent; batch_id is empty for an automation's email.
CREATE TABLE IF NOT EXISTS deliveries (
    token TEXT PRIMARY KEY,
    batch_id INTEGER REFERENCES email_batches(id) ON DELETE CASCADE,
    contact_id INTEGER, email TEXT NOT NULL, sent_at TEXT NOT NULL);

-- Raw events, written the moment they happen; the worker ingests them later.
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, batch_id INTEGER,
    email TEXT, action TEXT, reference TEXT, credits INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, ingested_at TEXT);

-- Ingested engagement: what the email batch report reads.
CREATE TABLE IF NOT EXISTS engagement (
    id INTEGER PRIMARY KEY, batch_id INTEGER, email TEXT NOT NULL,
    kind TEXT NOT NULL, at TEXT NOT NULL);

-- Ingested billing: one row per billable action.
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY, action TEXT NOT NULL, reference TEXT NOT NULL,
    credits INTEGER NOT NULL, at TEXT NOT NULL);

-- Written synchronously for every action, billable or not.
CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY, action TEXT NOT NULL, detail TEXT NOT NULL,
    credits INTEGER NOT NULL, at TEXT NOT NULL);
"""

FORMAT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


def now(offset_s: float = 0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=offset_s)).strftime(FORMAT)


def to_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime(FORMAT)


def connect() -> sqlite3.Connection:
    SETTINGS.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SETTINGS.db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def tx():
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@contextmanager
def read():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
    with tx() as conn:
        if conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]:
            return
        stamp = now()
        # Not the run's contacts: the suite must never mail them.
        for i, (first, last) in enumerate([("Demo", "Reader"), ("Sample", "Subscriber"),
                                           ("Preview", "Member")], 1):
            conn.execute("INSERT INTO contacts (email, first_name, last_name, created_at) "
                         "VALUES (?, ?, ?, ?)", (f"reader{i}@example.net", first, last, stamp))
        conn.execute("INSERT INTO suppression_lists (name, created_at) VALUES (?, ?)",
                     ("Do not mail", stamp))
