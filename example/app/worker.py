"""The worker: sends due email batches and automation emails, and ingests events
after a delay.

Stats and billing are deliberately asynchronous: an open, a click, a delivery or
a charge is written as a raw event the moment it happens, and only reaches the
report and the billing journal DEMO_ESP_INGEST_DELAY_S later. That is the shape
of a real ingestion pipeline, and what the suite's staged verification is for.

    python -m example.app.worker
"""
import secrets
import signal
import threading

from example.app import bugs, db, logic, mail
from example.app.settings import SETTINGS


def _claim(batch_id: int) -> bool:
    """Move a due email batch to 'sending'; False when another worker got it first."""
    with db.tx() as conn:
        cur = conn.execute("UPDATE email_batches SET status = 'sending' WHERE id = ? AND "
                           "status IN ('queued', 'scheduled')", (batch_id,))
        return cur.rowcount == 1


def send_batch(batch_id: int):
    with db.read() as conn:
        batch = logic.get_batch(conn, batch_id)
        people = logic.recipients(conn, batch)
    links = mail.links_in(batch["body_html"])
    tokens = {p["id"]: secrets.token_urlsafe(16) for p in people}
    messages = []
    for person in people:
        token = tokens[person["id"]]
        messages.append(mail.build(mail.render(batch, person, token, links),
                                   person["email"], token))
    try:
        mail.send_all(messages)
    except OSError as exc:
        with db.tx() as conn:
            conn.execute("UPDATE email_batches SET status = 'failed' WHERE id = ?",
                         (batch_id,))
            logic.log_usage(conn, "batch.failed", f"{batch['name']}: {exc}")
        return
    stamp = db.now()
    with db.tx() as conn:
        for idx, url in enumerate(links):
            conn.execute("INSERT OR REPLACE INTO email_batch_links VALUES (?, ?, ?)",
                         (batch_id, idx, url))
        for person in people:
            conn.execute("INSERT INTO deliveries VALUES (?, ?, ?, ?, ?)",
                         (tokens[person["id"]], batch_id, person["id"],
                          person["email"], stamp))
            conn.execute("INSERT INTO events (kind, batch_id, email, created_at) "
                         "VALUES ('delivered', ?, ?, ?)", (batch_id, person["email"], stamp))
        conn.execute("UPDATE email_batches SET status = 'sent', sent_at = ?, recipients = ? "
                     "WHERE id = ?", (stamp, len(people), batch_id))
        logic.log_usage(conn, "batch.send", batch["name"], len(people))
        if people:
            logic.queue_charge(conn, "batch.send", f"batch:{batch_id}", len(people))


def send_due() -> int:
    with db.read() as conn:
        due = [r["id"] for r in conn.execute(
            "SELECT id FROM email_batches WHERE status IN ('queued', 'scheduled') "
            "AND scheduled_at <= ? ORDER BY id", (db.now(),))]
    sent = 0
    for batch_id in due:
        if _claim(batch_id):
            send_batch(batch_id)
            sent += 1
    return sent


def _finish_run(run_id: int, status: str, reason: str = None, sent_at: str = None):
    with db.tx() as conn:
        conn.execute("UPDATE automation_runs SET status = ?, reason = ?, sent_at = ? "
                     "WHERE id = ?", (status, reason, sent_at, run_id))


def send_run(run: dict):
    """Email one contact whose automation delay is up. The contact is read again
    now, so an unsubscribe during the delay is honoured."""
    with db.read() as conn:
        automation = conn.execute("SELECT * FROM automations WHERE id = ?",
                                  (run["automation_id"],)).fetchone()
        contact = conn.execute("SELECT * FROM contacts WHERE id = ?",
                               (run["contact_id"],)).fetchone()
    if automation is None or contact is None:
        _finish_run(run["id"], "skipped", "the contact or automation no longer exists")
        return
    if contact["status"] != "subscribed" and not bugs.active("automation_ignores_unsubscribe"):
        _finish_run(run["id"], "skipped", "unsubscribed")
        return
    token = secrets.token_urlsafe(16)
    try:
        mail.send_all([mail.build(mail.render(dict(automation), dict(contact), token, []),
                                  contact["email"], token)])
    except OSError as exc:
        _finish_run(run["id"], "failed", str(exc))
        return
    stamp = db.now()
    with db.tx() as conn:
        conn.execute("INSERT INTO deliveries VALUES (?, NULL, ?, ?, ?)",
                     (token, contact["id"], contact["email"], stamp))
        conn.execute("UPDATE automation_runs SET status = 'sent', sent_at = ? WHERE id = ?",
                     (stamp, run["id"]))
        logic.log_usage(conn, "automation.send", f"{automation['name']}: {contact['email']}")


def send_due_runs() -> int:
    """Automation runs whose delay is up, each claimed once ('waiting' -> 'sending')."""
    with db.read() as conn:
        due = [dict(r) for r in conn.execute(
            "SELECT * FROM automation_runs WHERE status = 'waiting' AND due_at <= ? "
            "ORDER BY id", (db.now(),))]
    sent = 0
    for run in due:
        with db.tx() as conn:
            claimed = conn.execute("UPDATE automation_runs SET status = 'sending' WHERE id = ? "
                                   "AND status = 'waiting'", (run["id"],)).rowcount
        if claimed:
            send_run(run)
            sent += 1
    return sent


def ingest() -> int:
    """Land every event older than the ingestion delay."""
    cutoff = db.now(-SETTINGS.ingest_delay_s)
    with db.tx() as conn:
        rows = conn.execute("SELECT * FROM events WHERE ingested_at IS NULL AND "
                            "created_at <= ? ORDER BY id", (cutoff,)).fetchall()
        for event in rows:
            if event["kind"] == "charge":
                conn.execute("INSERT INTO journal (action, reference, credits, at) "
                             "VALUES (?, ?, ?, ?)", (event["action"], event["reference"],
                                                     event["credits"], db.now()))
            else:
                conn.execute("INSERT INTO engagement (batch_id, email, kind, at) "
                             "VALUES (?, ?, ?, ?)", (event["batch_id"], event["email"],
                                                     event["kind"], event["created_at"]))
            conn.execute("UPDATE events SET ingested_at = ? WHERE id = ?",
                         (db.now(), event["id"]))
    return len(rows)


def tick():
    send_due()
    send_due_runs()
    ingest()


def run_forever(stop: threading.Event = None):
    stop = stop or threading.Event()
    db.init()
    print(f"[worker] ingest delay {SETTINGS.ingest_delay_s}s, tick {SETTINGS.worker_tick_s}s",
          flush=True)
    while not stop.is_set():
        try:
            tick()
        except Exception as exc:  # one bad tick must not stop the worker
            print(f"[worker] tick failed: {type(exc).__name__}: {exc}", flush=True)
        stop.wait(SETTINGS.worker_tick_s)


def start_in_thread() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(stop,), daemon=True, name="worker").start()
    return stop


if __name__ == "__main__":
    halt = threading.Event()
    # As a container's PID 1, an unhandled SIGTERM is ignored and ends in SIGKILL.
    signal.signal(signal.SIGTERM, lambda *_: halt.set())
    try:
        run_forever(halt)
    except KeyboardInterrupt:
        pass
    print("[worker] stopped", flush=True)
