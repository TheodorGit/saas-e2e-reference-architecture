# The test runner: the app's slim Python base, Playwright with Chromium only, this
# repo, and a virtual screen with a web viewer so the UI tests can be watched live.
FROM python:3.12-slim

# The bytecode prefix keeps a mounted host checkout's __pycache__ out of play.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX=/tmp/pycache \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Xvfb is the virtual screen, x11vnc serves it, and noVNC shows it in a browser.
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*
# The live view's front page opens the viewer straight away, watch-only, scaled.
RUN cp -r /usr/share/novnc /opt/live \
    && printf '%s' '<!doctype html><meta charset="utf-8"><title>Live UI tests</title><meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=true&amp;view_only=true&amp;resize=scale&amp;reconnect=true">' > /opt/live/index.html

# Chromium and its system libraries, before the code: a code change rebuilds only
# the layers below, never the browser.
RUN pip install --no-cache-dir "playwright==1.63.0" \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml README.md ./
COPY framework framework
COPY example example
RUN pip install --no-cache-dir -e .

EXPOSE 7900
CMD ["bash", "example/suite/entrypoint.sh"]
