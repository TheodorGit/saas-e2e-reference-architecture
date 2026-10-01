"""Signing in through the UI."""
import pytest

from example.suite.pages.dashboard import DashboardPage
from example.suite.pages.login import LoginPage

pytestmark = pytest.mark.pipeline


def test_login(anon_page, config, steps):
    login = LoginPage(anon_page)
    login.open()

    def refused():
        message = login.sign_in_refused(config.email, "not-the-password")
        assert "incorrect" in message, f"the refusal does not say why: {message!r}"
        return message
    steps.step("wrong password is refused", refused,
               expected="an error on the login screen, and no way in", ui=True)

    steps.step("sign in", lambda: login.sign_in(config.email, config.password),
               expected="the dashboard opens", ui=True)
    steps.step("the dashboard paints its numbers",
               lambda: DashboardPage(anon_page).value("credits"),
               expected="the credit balance shows a number, not its placeholder", ui=True)
