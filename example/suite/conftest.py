"""The Demo ESP App suite on the framework plugin.

Fixtures here are product wiring only: where the app is, how to sign in, how a
created thing is removed. Stage order, the ledger, steps, reports and
destructive gating all come from the framework plugin.
"""
import shutil
import tempfile

import pytest
import requests
from playwright.sync_api import expect

from example.suite import config as suite_config
from example.suite import ledger_kinds as kinds
from example.suite import profile  # noqa: F401  (registers the report profile)
from example.suite.app_client import AppApi, AppError, PublicApi
from framework import tokens
from framework.delivery.mailpit import MailpitClient
from framework.ui import tracing

pytest_plugins = ["framework.pytest_plugin"]

UI_TIMEOUT_MS = 15_000
STAGES = ("example/suite/tests/baseline/ = 0",
          "example/suite/tests/actions/ = 1",
          "example/suite/tests/api/ = 1",
          "example/suite/tests/verification/ = 2")


def pytest_configure(config):
    # The plugin's e2e_stages ini option, set here so it exists only with the plugin.
    for line in STAGES:
        config.addinivalue_line("e2e_stages", line)


@pytest.fixture(scope="session")
def config():
    return suite_config.load()


@pytest.fixture(scope="session")
def app_api(config):
    """The signed-in app API. A stack that cannot be reached fails loudly."""
    try:
        requests.get(f"{config.base_url}/health", timeout=10).raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Demo ESP App is not reachable at {config.base_url}: {exc}") from exc
    return AppApi(config.base_url, config.email, config.password)


@pytest.fixture(scope="session")
def public_api(config):
    return PublicApi(config.base_url, config.api_token)


@pytest.fixture(scope="session")
def inbox(config):
    try:
        requests.get(f"{config.mailpit_url}/api/v1/messages", timeout=10).raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Mailpit is not reachable at {config.mailpit_url}: {exc}") from exc
    return MailpitClient(config.mailpit_url)


@pytest.fixture
def v1(api_recorder, config):
    """The public API with a Bearer token, every call a recorded step."""
    http = requests.Session()
    http.headers["Authorization"] = f"Bearer {config.api_token}"
    return api_recorder(http, config.base_url)


@pytest.fixture
def v1_anon(api_recorder, config):
    """The public API without a token."""
    return api_recorder(requests.Session(), config.base_url, label="without a token: ")


@pytest.fixture
def record(e2e_ledger, request):
    """ledger.record, stamped with the test that recorded it."""
    def write(action: str, kind: str, **fields):
        return e2e_ledger.record(action, kind, test=request.node.nodeid, **fields)
    return write


@pytest.fixture
def make_contact(app_api, record, e2e_ledger, entity_name, config):
    """Factory: a run-owned contact created through the API, recorded and
    registered for cleanup."""
    def make(slug: str, tags=(), first_name: str = "", last_name: str = "",
             status: str = "subscribed") -> dict:
        token = entity_name(slug)
        contact = app_api.add_contact(config.address(token), first_name, last_name, tags,
                                      status)
        e2e_ledger.register_entity("contact", contact["id"], contact["email"])
        record("contact.add", kinds.CONTACT, name=token, email=contact["email"],
               contacts_delta=1, subscribed_delta=int(status == "subscribed"))
        return contact
    return make


@pytest.fixture
def make_suppression(app_api, e2e_ledger, entity_name):
    def make(slug: str, emails) -> dict:
        found = app_api.create_suppression(entity_name(slug), emails)
        e2e_ledger.register_entity("suppression", found["id"], found["name"])
        return found
    return make


# --- browser ----------------------------------------------------------------------

def _page(browser, config, steps, request, cookie: str = None):
    """A hand-built context and page with screen evidence (video, trace, a screen
    per UI check), kept only when a UI check fails."""
    expect.set_options(timeout=UI_TIMEOUT_MS)
    # Recorded outside the reports: a video is copied in only if it is evidence.
    video_dir = tempfile.mkdtemp(prefix="e2e-video-")
    context = browser.new_context(base_url=config.base_url, accept_downloads=True,
                                  record_video_dir=video_dir)
    if cookie:
        context.add_cookies([{"name": "esp_session", "value": cookie, "url": config.base_url}])
    context.set_default_timeout(UI_TIMEOUT_MS)
    page = context.new_page()
    screen = tracing.Evidence(context, page, steps)
    yield page
    # Closes the context, which finishes the video.
    screen.stop(tokens.run_dir(), tracing.failed(steps, request.node))
    shutil.rmtree(video_dir, ignore_errors=True)


@pytest.fixture
def app_page(browser, config, app_api, steps, request):
    """A signed-in page (the login test signs in through the UI instead)."""
    yield from _page(browser, config, steps, request, cookie=app_api.session_cookie)


@pytest.fixture
def anon_page(browser, config, steps, request):
    """A page with no session: a visitor, or a recipient following a link."""
    yield from _page(browser, config, steps, request)


# --- cleanup ----------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def cleanup(e2e_ledger):
    """Remove what the run created and no failure preserved as evidence.
    Depends on the ledger, so it runs before the ledger's final save."""
    yield
    ledger = e2e_ledger
    if ledger.replay_of:
        return
    cfg = suite_config.load()
    targets = ledger.cleanup_targets()
    if not targets:
        return
    api = AppApi(cfg.base_url, cfg.email, cfg.password)
    removers = {
        "contact": api.delete_contact,
        "suppression": api.delete_suppression,
        "automation": api.delete_automation,
        "mail": lambda token: MailpitClient(cfg.mailpit_url).delete_matching(subject=token),
    }
    for entity in targets:
        try:
            removers[entity["kind"]](entity["id"])
            ledger.mark_removed(entity["id"])
        except (AppError, requests.RequestException) as exc:
            print(f"[cleanup] could not remove {entity['kind']} {entity['name']}: {exc}")
