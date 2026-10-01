"""The Demo ESP App's HTTP surface.

    /                 the single-page app (static files, no build step)
    /api/...          JSON for the app, behind the session cookie
    /v1/...           the public JSON API, behind a Bearer token; /v1/ indexes it
    /t/o, /t/c        open pixel and click tracker
    /u/{token}        public unsubscribe/resubscribe page and one-click endpoint

    uvicorn example.app.main:app
"""
import base64
import hmac
import html
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from example.app import bugs, db, logic, worker
from example.app.settings import SETTINGS

STATIC = Path(__file__).parent / "static"
SESSION_COOKIE = "esp_session"
PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@asynccontextmanager
async def lifespan(_app):
    db.init()
    stop = worker.start_in_thread() if SETTINGS.inprocess_worker else None
    yield
    if stop:
        stop.set()


app = FastAPI(title="Demo ESP App", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(logic.Invalid)
async def _invalid(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(logic.NotFound)
async def _not_found(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=404)


def simulated_latency():
    # Deliberate: a real backend is not instant, and the UI's async edges must show.
    time.sleep(SETTINGS.ui_latency_ms / 1000)


# --- auth ---------------------------------------------------------------------

def session_user(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE, "")
    with db.read() as conn:
        found = token and conn.execute("SELECT 1 FROM sessions WHERE token = ?",
                                       (token,)).fetchone()
    if not found:
        raise HTTPException(401, "not signed in")
    return SETTINGS.demo_email


def api_client(authorization: str = Header(default="")) -> str:
    scheme, _, token = authorization.partition(" ")
    if bugs.active("api_ignores_auth"):
        return "api"
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.strip(),
                                                             SETTINGS.api_token):
        raise HTTPException(401, "a valid Bearer token is required",
                            headers={"WWW-Authenticate": "Bearer"})
    return "api"


class Login(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def login(body: Login):
    ok = (body.email.strip().lower() == SETTINGS.demo_email and
          (hmac.compare_digest(body.password, SETTINGS.demo_password)
           or bugs.active("login_accepts_any_password")))
    if not ok:
        raise HTTPException(401, "email or password is incorrect")
    token = secrets.token_urlsafe(24)
    with db.tx() as conn:
        conn.execute("INSERT INTO sessions VALUES (?, ?)", (token, db.now()))
    response = JSONResponse({"email": SETTINGS.demo_email})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/api/logout")
def logout(request: Request):
    with db.tx() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?",
                     (request.cookies.get(SESSION_COOKIE, ""),))
    response = JSONResponse({"signed_out": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/me")
def me(user: str = Depends(session_user)):
    return {"email": user}


# --- app API (session) ----------------------------------------------------------

class NewContact(BaseModel):
    email: str
    first_name: str = ""
    last_name: str = ""
    tags: list[str] = []
    status: str = "subscribed"


class BulkTag(BaseModel):
    ids: list[int]
    tag: str
    action: str = "add"


class Validate(BaseModel):
    email: str


class NewSuppression(BaseModel):
    name: str
    emails: list[str] = []


class Emails(BaseModel):
    emails: list[str]


class NewBatch(BaseModel):
    name: str
    subject: str
    body_html: str
    audience_tag: str | None = None
    suppression_list_ids: list[int] = []
    send_at: str | None = None


class NewAutomation(BaseModel):
    name: str
    trigger_tag: str
    delay_s: int
    subject: str
    body_html: str


signed_in = [Depends(session_user)]


@app.get("/api/dashboard", dependencies=signed_in)
def dashboard():
    simulated_latency()
    with db.read() as conn:
        return logic.dashboard(conn)


@app.get("/api/contacts", dependencies=signed_in)
def contacts(q: str = "", tag: str = ""):
    simulated_latency()
    with db.read() as conn:
        return logic.list_contacts(conn, q.strip(), tag.strip())


@app.post("/api/contacts", dependencies=signed_in, status_code=201)
def add_contact(body: NewContact):
    simulated_latency()
    with db.tx() as conn:
        return logic.add_contact(conn, body.email, body.first_name, body.last_name, body.tags,
                                 body.status)


@app.delete("/api/contacts/{contact_id}", dependencies=signed_in)
def delete_contact(contact_id: int):
    with db.tx() as conn:
        if bugs.active("delete_not_persisted"):
            return logic.get_contact(conn, contact_id)
        return logic.delete_contact(conn, contact_id)


@app.post("/api/contacts/bulk-tag", dependencies=signed_in)
def bulk_tag(body: BulkTag):
    if body.action not in ("add", "remove"):
        raise logic.Invalid("action must be 'add' or 'remove'")
    with db.tx() as conn:
        return logic.bulk_tag(conn, body.ids, body.tag, remove=body.action == "remove")


@app.get("/api/contacts/export", dependencies=signed_in)
def export_contacts(q: str = "", tag: str = ""):
    with db.read() as conn:
        body = logic.export_csv(conn, q.strip(), tag.strip())
    return PlainTextResponse(body, media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="contacts.csv"'})


@app.get("/api/tags", dependencies=signed_in)
def tags():
    with db.read() as conn:
        return logic.all_tags(conn)


@app.post("/api/validate", dependencies=signed_in)
def validate(body: Validate):
    with db.tx() as conn:
        return logic.validate_address(conn, body.email)


@app.get("/api/address-suppression-lists", dependencies=signed_in)
def suppression_lists():
    with db.read() as conn:
        return logic.list_suppression(conn)


@app.post("/api/address-suppression-lists", dependencies=signed_in, status_code=201)
def create_suppression(body: NewSuppression):
    with db.tx() as conn:
        return logic.create_suppression(conn, body.name, body.emails)


@app.get("/api/address-suppression-lists/{list_id}", dependencies=signed_in)
def suppression_list(list_id: int):
    with db.read() as conn:
        return logic.suppression(conn, list_id)


@app.post("/api/address-suppression-lists/{list_id}/entries", dependencies=signed_in)
def add_suppressed(list_id: int, body: Emails):
    with db.tx() as conn:
        logic.add_suppressed(conn, list_id, body.emails)
        return logic.suppression(conn, list_id)


@app.delete("/api/address-suppression-lists/{list_id}", dependencies=signed_in)
def delete_suppression(list_id: int):
    with db.tx() as conn:
        return logic.delete_suppression(conn, list_id)


@app.get("/api/email-batches", dependencies=signed_in)
def email_batches():
    with db.read() as conn:
        return logic.list_batches(conn)


@app.post("/api/email-batches", dependencies=signed_in, status_code=201)
def create_batch(body: NewBatch):
    with db.tx() as conn:
        return logic.create_batch(conn, **body.model_dump())


@app.get("/api/email-batches/{batch_id}", dependencies=signed_in)
def email_batch(batch_id: int):
    with db.read() as conn:
        return logic.get_batch(conn, batch_id)


@app.get("/api/email-batches/{batch_id}/report", dependencies=signed_in)
def batch_report(batch_id: int):
    simulated_latency()
    with db.read() as conn:
        return logic.report(conn, batch_id)


@app.post("/api/automations", dependencies=signed_in, status_code=201)
def create_automation(body: NewAutomation):
    with db.tx() as conn:
        return logic.create_automation(conn, **body.model_dump())


@app.get("/api/automations/{automation_id}", dependencies=signed_in)
def automation(automation_id: int):
    with db.read() as conn:
        return logic.get_automation(conn, automation_id)


@app.delete("/api/automations/{automation_id}", dependencies=signed_in)
def delete_automation(automation_id: int):
    with db.tx() as conn:
        return logic.delete_automation(conn, automation_id)


@app.get("/api/credits", dependencies=signed_in)
def credits():
    with db.read() as conn:
        return {"balance": logic.balance(conn), "journal": logic.journal(conn)}


@app.get("/api/usage", dependencies=signed_in)
def usage():
    with db.read() as conn:
        return logic.usage(conn)


# --- public API (Bearer) ------------------------------------------------------------

bearer = [Depends(api_client)]


@app.get("/v1/contacts", dependencies=bearer, summary="List contacts; filter by q and tag")
def v1_contacts(q: str = "", tag: str = ""):
    with db.read() as conn:
        return logic.list_contacts(conn, q.strip(), tag.strip())


@app.post("/v1/contacts", dependencies=bearer, status_code=201, summary="Add a contact")
def v1_add_contact(body: NewContact):
    tags = [] if bugs.active("api_contact_tags_dropped") else body.tags
    with db.tx() as conn:
        return logic.add_contact(conn, body.email, body.first_name, body.last_name, tags,
                                 body.status)


@app.get("/v1/contacts/{contact_id}", dependencies=bearer, summary="Read one contact")
def v1_contact(contact_id: int):
    with db.read() as conn:
        return logic.get_contact(conn, contact_id)


@app.delete("/v1/contacts/{contact_id}", dependencies=bearer, summary="Delete a contact")
def v1_delete_contact(contact_id: int):
    with db.tx() as conn:
        return logic.delete_contact(conn, contact_id)


@app.post("/v1/validate", dependencies=bearer, summary="Validate one address (billed)")
def v1_validate(body: Validate):
    with db.tx() as conn:
        result = logic.validate_address(conn, body.email)
    if bugs.active("api_validation_reports_zero_cost"):
        result = {**result, "cost": 0, "free": True}
    return result


@app.get("/v1/address-suppression-lists", dependencies=bearer,
         summary="List address suppression lists")
def v1_suppression_lists():
    with db.read() as conn:
        return logic.list_suppression(conn)


@app.get("/v1/email-batches", dependencies=bearer, summary="List email batches")
def v1_email_batches():
    with db.read() as conn:
        return logic.list_batches(conn)


@app.get("/v1/email-batches/{batch_id}/report", dependencies=bearer,
         summary="Delivered, open and click counts with the addresses behind them")
def v1_report(batch_id: int):
    with db.read() as conn:
        return logic.report(conn, batch_id)


@app.get("/v1/credits", dependencies=bearer, summary="Credit balance and billing journal")
def v1_credits():
    with db.read() as conn:
        balance = SETTINGS.credit_grant if bugs.active("api_balance_stale") else \
            logic.balance(conn)
        return {"balance": balance, "journal": logic.journal(conn)}


if bugs.active("api_endpoint_without_test"):
    @app.get("/v1/address-suppression-lists/{list_id}", dependencies=bearer,
             summary="Read one address suppression list")
    def v1_suppression_list(list_id: int):
        with db.read() as conn:
            return logic.suppression(conn, list_id)


@app.get("/v1/", summary="Index of the documented endpoints")
def v1_index():
    """Public: built from the routes themselves, so it cannot drift from them."""
    endpoints = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/v1/"):
            for method in sorted(route.methods):
                endpoints.append({"method": method, "path": route.path,
                                  "summary": route.summary or "",
                                  "auth": "none" if route.path == "/v1/" else "bearer"})
    return {"name": "Demo ESP App public API", "version": "1", "endpoints": endpoints}


# --- tracking and public pages ------------------------------------------------------

def _delivery(conn, token: str):
    row = conn.execute("SELECT * FROM deliveries WHERE token = ?", (token,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown link")
    return row


def _event(conn, kind: str, delivery):
    conn.execute("INSERT INTO events (kind, batch_id, email, created_at) "
                 "VALUES (?, ?, ?, ?)", (kind, delivery["batch_id"], delivery["email"],
                                         db.now()))


@app.get("/t/o/{token}.gif", include_in_schema=False)
def open_pixel(token: str):
    with db.tx() as conn:
        _event(conn, "open", _delivery(conn, token))
    return Response(PIXEL, media_type="image/gif", headers={"Cache-Control": "no-store"})


@app.get("/t/c/{token}/{idx}", include_in_schema=False)
def click(token: str, idx: int):
    with db.tx() as conn:
        delivery = _delivery(conn, token)
        link = conn.execute("SELECT url FROM email_batch_links WHERE batch_id = ? AND "
                            "idx = ?", (delivery["batch_id"], idx)).fetchone()
        if not link:
            raise HTTPException(404, "unknown link")
        _event(conn, "click", delivery)
    return RedirectResponse(link["url"], status_code=302)


def _preferences_page(email: str, status: str, token: str, note: str = "") -> HTMLResponse:
    subscribed = status == "subscribed"
    action, label = ("unsubscribe", "Unsubscribe") if subscribed else \
        ("resubscribe", "Resubscribe")
    state = (f"You are subscribed as {html.escape(email)}." if subscribed else
             f"{html.escape(email)} is unsubscribed. You will no longer receive emails "
             f"from Demo ESP App.")
    notice = f'<p role="status">{html.escape(note)}</p>' if note else ""
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Email preferences - Demo ESP App</title>'
        '<link rel="stylesheet" href="/static/app.css"></head>'
        '<body class="public"><main class="card narrow"><h1>Email preferences</h1>'
        f'{notice}<p data-testid="subscription-state">{state}</p>'
        f'<form method="post" action="/u/{html.escape(token)}">'
        f'<input type="hidden" name="action" value="{action}">'
        f'<button type="submit" class="primary">{label}</button></form></main></body></html>')


def _contact_status(conn, email: str) -> str:
    row = conn.execute("SELECT status FROM contacts WHERE email = ?", (email,)).fetchone()
    if not row:
        raise HTTPException(404, "this address is no longer a contact")
    return row["status"]


@app.get("/u/{token}", response_class=HTMLResponse, include_in_schema=False)
def preferences(token: str):
    with db.read() as conn:
        delivery = _delivery(conn, token)
        return _preferences_page(delivery["email"], _contact_status(conn, delivery["email"]),
                                 token)


@app.post("/u/{token}", response_class=HTMLResponse, include_in_schema=False)
async def change_preferences(token: str, request: Request):
    form = await request.form()
    action = form.get("action")
    if action not in ("unsubscribe", "resubscribe"):
        raise HTTPException(400, "action must be unsubscribe or resubscribe")
    status = "unsubscribed" if action == "unsubscribe" else "subscribed"
    with db.tx() as conn:
        delivery = _delivery(conn, token)
        _contact_status(conn, delivery["email"])
        if not (action == "resubscribe" and bugs.active("resubscribe_ignored")):
            logic.set_status(conn, delivery["email"], status)
        _event(conn, action, delivery)
        if action == "unsubscribe" and bugs.active("unsubscribe_counts_click"):
            _event(conn, "click", delivery)
    note = "You have been unsubscribed." if action == "unsubscribe" else \
        "Welcome back: you are subscribed again."
    return _preferences_page(delivery["email"], status, token, note)


@app.post("/u/{token}/one-click", include_in_schema=False)
async def one_click(token: str, request: Request):
    """RFC 8058: a mail client POSTs List-Unsubscribe=One-Click, no page, no login."""
    form = await request.form()
    if form.get("List-Unsubscribe") != "One-Click":
        raise HTTPException(400, "expected List-Unsubscribe=One-Click")
    with db.tx() as conn:
        delivery = _delivery(conn, token)
        _contact_status(conn, delivery["email"])
        result = logic.set_status(conn, delivery["email"], "unsubscribed")
        _event(conn, "unsubscribe", delivery)
        if bugs.active("unsubscribe_counts_click"):
            _event(conn, "click", delivery)
    return result


@app.get("/landing", response_class=HTMLResponse, include_in_schema=False)
def landing():
    return HTMLResponse('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                        '<title>Demo ESP App</title></head><body><h1>Thanks for '
                        'reading</h1></body></html>')


@app.get("/api/flags", include_in_schema=False)
def flags():
    """The active defect switches; the front end reads its own from here."""
    return {"bugs": sorted(bugs.ACTIVE)}


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
