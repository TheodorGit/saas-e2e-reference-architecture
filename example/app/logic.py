"""The Demo ESP App's domain rules, shared by the session API and the public API."""
import csv
import io
import json
import re
import sqlite3

from example.app import bugs, db
from example.app.settings import SETTINGS

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLE_ACCOUNTS = {"info", "admin", "support", "sales", "noreply", "no-reply"}
STATUSES = ("subscribed", "unsubscribed")


class Invalid(ValueError):
    ...


class NotFound(LookupError):
    pass


def normalise_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not EMAIL.match(email):
        raise Invalid(f"not a valid email address: {value!r}")
    return email


def log_usage(conn, action: str, detail: str, credits: int = 0):
    conn.execute("INSERT INTO usage_log (action, detail, credits, at) VALUES (?, ?, ?, ?)",
                 (action, detail, credits, db.now()))


def queue_charge(conn, action: str, reference: str, credits: int):
    conn.execute("INSERT INTO events (kind, action, reference, credits, created_at) "
                 "VALUES ('charge', ?, ?, ?, ?)", (action, reference, credits, db.now()))


def _contact(conn, row) -> dict:
    tags = [r["tag"] for r in conn.execute(
        "SELECT tag FROM contact_tags WHERE contact_id = ? ORDER BY tag", (row["id"],))]
    return {"id": row["id"], "email": row["email"], "first_name": row["first_name"],
            "last_name": row["last_name"], "status": row["status"], "tags": tags,
            "created_at": row["created_at"]}


def _contact_rows(conn, q: str = "", tag: str = "", limit: int = 500):
    sql = "SELECT * FROM contacts c WHERE 1=1"
    args: list = []
    if q:
        sql += " AND (c.email LIKE ? OR c.first_name LIKE ? OR c.last_name LIKE ?)"
        args += [f"%{q}%"] * 3
    if tag:
        sql += " AND EXISTS (SELECT 1 FROM contact_tags t WHERE t.contact_id = c.id " \
               "AND t.tag = ?)"
        args.append(tag)
    sql += " ORDER BY c.id DESC LIMIT ?"
    args.append(limit)
    return conn.execute(sql, args).fetchall()


def list_contacts(conn, q: str = "", tag: str = "", limit: int = 500) -> dict:
    rows = _contact_rows(conn, q, tag, limit)
    return {"items": [_contact(conn, r) for r in rows], "count": len(rows)}


def get_contact(conn, contact_id: int) -> dict:
    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if not row:
        raise NotFound(f"contact {contact_id} not found")
    return _contact(conn, row)


def add_contact(conn, email: str, first_name: str = "", last_name: str = "",
                tags=(), status: str = "subscribed") -> dict:
    email = normalise_email(email)
    if status not in STATUSES:
        raise Invalid(f"status must be one of {STATUSES}")
    try:
        cur = conn.execute(
            "INSERT INTO contacts (email, first_name, last_name, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (email, (first_name or "").strip(), (last_name or "").strip(), status, db.now()))
    except sqlite3.IntegrityError as exc:
        raise Invalid(f"{email} is already a contact") from exc
    for tag in _tags(tags):
        conn.execute("INSERT OR IGNORE INTO contact_tags VALUES (?, ?)", (cur.lastrowid, tag))
        enroll(conn, cur.lastrowid, email, tag)
    log_usage(conn, "contact.add", email)
    return get_contact(conn, cur.lastrowid)


def delete_contact(conn, contact_id: int) -> dict:
    contact = get_contact(conn, contact_id)
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    log_usage(conn, "contact.delete", contact["email"])
    return contact


def _tags(tags) -> list[str]:
    return sorted({t.strip() for t in tags or () if t and t.strip()})


def bulk_tag(conn, contact_ids: list[int], tag: str, remove: bool = False) -> dict:
    tag = (tag or "").strip()
    if not tag:
        raise Invalid("a tag is required")
    if not contact_ids:
        raise Invalid("select at least one contact")
    changed = 0
    for contact_id in contact_ids:
        contact = get_contact(conn, contact_id)
        if remove:
            cur = conn.execute("DELETE FROM contact_tags WHERE contact_id = ? AND tag = ?",
                               (contact_id, tag))
        else:
            cur = conn.execute("INSERT OR IGNORE INTO contact_tags VALUES (?, ?)",
                               (contact_id, tag))
            if cur.rowcount:
                enroll(conn, contact_id, contact["email"], tag)
        changed += cur.rowcount
    log_usage(conn, "contact.untag" if remove else "contact.tag",
              f"{tag} on {len(contact_ids)} contact(s)")
    return {"tag": tag, "selected": len(contact_ids), "changed": changed}


def all_tags(conn) -> list[str]:
    return [r["tag"] for r in conn.execute(
        "SELECT DISTINCT tag FROM contact_tags ORDER BY tag")]


def set_status(conn, email: str, status: str) -> dict:
    if status not in STATUSES:
        raise Invalid(f"status must be one of {STATUSES}")
    email = normalise_email(email)
    cur = conn.execute("UPDATE contacts SET status = ? WHERE email = ?", (status, email))
    if not cur.rowcount:
        raise NotFound(f"no contact {email}")
    log_usage(conn, "contact." + ("unsubscribe" if status == "unsubscribed" else
                                  "resubscribe"), email)
    return {"email": email, "status": status}


def export_csv(conn, q: str = "", tag: str = "") -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["email", "first_name", "last_name", "status", "tags"])
    if bugs.active("export_ignores_filter"):
        q, tag = "", ""
    for row in _contact_rows(conn, q, tag, limit=100000):
        contact = _contact(conn, row)
        writer.writerow([contact["email"], contact["first_name"], contact["last_name"],
                         contact["status"], " ".join(contact["tags"])])
    return out.getvalue()


def _verdict(email: str) -> str:
    local = email.split("@", 1)[0]
    if "bounce" in local:
        return "invalid"
    if local in ROLE_ACCOUNTS:
        return "risky"
    return "valid"


def validate_address(conn, email: str) -> dict:
    email = normalise_email(email)
    since = db.now(-SETTINGS.validation_free_window_s)
    billed = conn.execute(
        "SELECT validated_at FROM validations WHERE email = ? AND cost > 0 AND "
        "validated_at >= ? ORDER BY validated_at DESC LIMIT 1", (email, since)).fetchone()
    if bugs.active("free_window_ignored"):
        billed = None
    cost = 0 if billed else SETTINGS.validation_cost
    result = _verdict(email)
    cur = conn.execute("INSERT INTO validations (email, result, cost, validated_at) "
                       "VALUES (?, ?, ?, ?)", (email, result, cost, db.now()))
    reference = f"validation:{cur.lastrowid}"
    log_usage(conn, "validation", email, cost)
    if cost:
        queue_charge(conn, "validation", reference, cost)
        if bugs.active("double_billing"):
            queue_charge(conn, "validation", reference, cost)
    return {"id": cur.lastrowid, "email": email, "result": result, "cost": cost,
            "free": cost == 0, "reference": reference,
            "free_window_s": SETTINGS.validation_free_window_s}


def list_suppression(conn) -> list[dict]:
    return [{"id": r["id"], "name": r["name"], "size": r["size"]} for r in conn.execute(
        "SELECT l.id, l.name, COUNT(e.email) AS size FROM suppression_lists l "
        "LEFT JOIN suppression_entries e ON e.list_id = l.id GROUP BY l.id ORDER BY l.id")]


def create_suppression(conn, name: str, emails=()) -> dict:
    name = (name or "").strip()
    if not name:
        raise Invalid("a list name is required")
    try:
        cur = conn.execute("INSERT INTO suppression_lists (name, created_at) VALUES (?, ?)",
                           (name, db.now()))
    except sqlite3.IntegrityError as exc:
        raise Invalid(f"a list named {name!r} already exists") from exc
    add_suppressed(conn, cur.lastrowid, emails)
    log_usage(conn, "suppression.create", name)
    return suppression(conn, cur.lastrowid)


def add_suppressed(conn, list_id: int, emails) -> int:
    suppression(conn, list_id)
    normalised = [normalise_email(e) for e in emails or () if e and e.strip()]
    for email in normalised:
        conn.execute("INSERT OR IGNORE INTO suppression_entries VALUES (?, ?)",
                     (list_id, email))
    return len(normalised)


def suppression(conn, list_id: int) -> dict:
    row = conn.execute("SELECT * FROM suppression_lists WHERE id = ?", (list_id,)).fetchone()
    if not row:
        raise NotFound(f"address suppression list {list_id} not found")
    emails = [r["email"] for r in conn.execute(
        "SELECT email FROM suppression_entries WHERE list_id = ? ORDER BY email", (list_id,))]
    return {"id": row["id"], "name": row["name"], "size": len(emails), "emails": emails}


def delete_suppression(conn, list_id: int) -> dict:
    found = suppression(conn, list_id)
    conn.execute("DELETE FROM suppression_lists WHERE id = ?", (list_id,))
    log_usage(conn, "suppression.delete", found["name"])
    return found


def _batch(row) -> dict:
    return {"id": row["id"], "name": row["name"], "subject": row["subject"],
            "body_html": row["body_html"], "audience_tag": row["audience_tag"],
            "suppression_list_ids": json.loads(row["suppression_list_ids"]),
            "status": row["status"], "scheduled_at": row["scheduled_at"],
            "sent_at": row["sent_at"], "recipients": row["recipients"],
            "created_at": row["created_at"]}


def create_batch(conn, name: str, subject: str, body_html: str,
                 audience_tag: str = None, suppression_list_ids=(),
                 send_at: str = None) -> dict:
    name, subject = (name or "").strip(), (subject or "").strip()
    if not name or not subject or not (body_html or "").strip():
        raise Invalid("name, subject and message are all required")
    for list_id in suppression_list_ids or ():
        suppression(conn, int(list_id))
    scheduled = db.to_utc(send_at) if send_at else db.now()
    status = "scheduled" if send_at and scheduled > db.now() else "queued"
    cur = conn.execute(
        "INSERT INTO email_batches (name, subject, body_html, audience_tag, "
        "suppression_list_ids, status, scheduled_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, subject, body_html, (audience_tag or "").strip() or None,
         json.dumps([int(i) for i in suppression_list_ids or ()]), status, scheduled,
         db.now()))
    log_usage(conn, "batch.schedule" if status == "scheduled" else "batch.queue", name)
    return get_batch(conn, cur.lastrowid)


def get_batch(conn, batch_id: int) -> dict:
    row = conn.execute("SELECT * FROM email_batches WHERE id = ?", (batch_id,)).fetchone()
    if not row:
        raise NotFound(f"email batch {batch_id} not found")
    return _batch(row)


def list_batches(conn) -> list[dict]:
    return [_batch(r) for r in conn.execute("SELECT * FROM email_batches ORDER BY id DESC")]


def recipients(conn, batch: dict) -> list[dict]:
    sql = "SELECT * FROM contacts c WHERE c.status = 'subscribed'"
    args: list = []
    if batch["audience_tag"]:
        sql += " AND EXISTS (SELECT 1 FROM contact_tags t WHERE t.contact_id = c.id " \
               "AND t.tag = ?)"
        args.append(batch["audience_tag"])
    ids = batch["suppression_list_ids"]
    if ids and not bugs.active("suppression_leak"):
        sql += (" AND c.email NOT IN (SELECT email FROM suppression_entries WHERE list_id "
                f"IN ({','.join('?' * len(ids))}))")
        args += ids
    return [dict(r) for r in conn.execute(sql + " ORDER BY c.id", args)]


def report(conn, batch_id: int) -> dict:
    batch = get_batch(conn, batch_id)
    lists = {}
    for kind in ("delivered", "open", "click"):
        lists[kind] = [r["email"] for r in conn.execute(
            "SELECT DISTINCT email FROM engagement WHERE batch_id = ? AND kind = ? "
            "ORDER BY email", (batch_id, kind))]
    if bugs.active("report_undercount"):
        lists["delivered"] = lists["delivered"][:-1]
    return {"batch": {k: batch[k] for k in ("id", "name", "subject", "status",
                                            "sent_at", "recipients")},
            "delivered": len(lists["delivered"]), "opens": len(lists["open"]),
            "clicks": len(lists["click"]), "delivered_to": lists["delivered"],
            "opened_by": lists["open"], "clicked_by": lists["click"]}


def create_automation(conn, name: str, trigger_tag: str, delay_s: int, subject: str,
                      body_html: str) -> dict:
    name, tag = (name or "").strip(), (trigger_tag or "").strip()
    subject = (subject or "").strip()
    if not name or not tag or not subject or not (body_html or "").strip():
        raise Invalid("name, trigger tag, subject and message are all required")
    if not 0 <= int(delay_s) <= 86400:
        raise Invalid("the delay must be between 0 and 86400 seconds")
    cur = conn.execute(
        "INSERT INTO automations (name, trigger_tag, delay_s, subject, body_html, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, tag, int(delay_s), subject, body_html, db.now()))
    log_usage(conn, "automation.create", name)
    return get_automation(conn, cur.lastrowid)


def get_automation(conn, automation_id: int) -> dict:
    row = conn.execute("SELECT * FROM automations WHERE id = ?",
                       (automation_id,)).fetchone()
    if not row:
        raise NotFound(f"automation {automation_id} not found")
    runs = [dict(r) for r in conn.execute(
        "SELECT id, contact_id, email, status, reason, enrolled_at, due_at, sent_at "
        "FROM automation_runs WHERE automation_id = ? ORDER BY id", (automation_id,))]
    return {**dict(row), "runs": runs}


def delete_automation(conn, automation_id: int) -> dict:
    found = get_automation(conn, automation_id)
    conn.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
    log_usage(conn, "automation.delete", found["name"])
    return found


def enroll(conn, contact_id: int, email: str, tag: str):
    for automation in conn.execute("SELECT id, delay_s FROM automations WHERE trigger_tag = ?",
                                   (tag,)).fetchall():
        conn.execute(
            "INSERT INTO automation_runs (automation_id, contact_id, email, status, "
            "enrolled_at, due_at) VALUES (?, ?, ?, 'waiting', ?, ?)",
            (automation["id"], contact_id, email, db.now(), db.now(automation["delay_s"])))
        log_usage(conn, "automation.enroll", email)


def balance(conn) -> int:
    spent = conn.execute("SELECT COALESCE(SUM(credits), 0) FROM journal").fetchone()[0]
    return SETTINGS.credit_grant - spent


def journal(conn, limit: int = 500) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, action, reference, credits, at FROM journal ORDER BY id DESC LIMIT ?",
        (limit,))]


def usage(conn, limit: int = 500) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, action, detail, credits, at FROM usage_log ORDER BY id DESC LIMIT ?",
        (limit,))]


def dashboard(conn) -> dict:
    count = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "credits": balance(conn),
        "contacts": count("SELECT COUNT(*) FROM contacts"),
        "subscribed": count("SELECT COUNT(*) FROM contacts WHERE status = 'subscribed'"),
        "batches_sent": count("SELECT COUNT(*) FROM email_batches WHERE status = 'sent'"),
    }
