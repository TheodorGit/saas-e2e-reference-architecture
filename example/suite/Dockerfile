# The test runner: Playwright's image (browsers included) plus this repo, and a
# virtual screen with a web viewer so the UI tests can be watched live.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

# Xvfb is the virtual screen, x11vnc serves it, and noVNC shows it in a browser.
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*
# The live view's front page opens the viewer straight away, watch-only, scaled.
RUN cp -r /usr/share/novnc /opt/live \
    && printf '%s' '<!doctype html><meta charset="utf-8"><title>Live UI tests</title><meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=true&amp;view_only=true&amp;resize=scale&amp;reconnect=true">' > /opt/live/index.html

# The bytecode prefix keeps a mounted host checkout's __pycache__ out of play.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX=/tmp/pycache
WORKDIR /srv

COPY pyproject.toml README.md ./
COPY framework framework
COPY example example
# Pinned to the browsers this image ships.
RUN pip install --no-cache-dir --break-system-packages "playwright==1.63.0" -e .

EXPOSE 7900
CMD ["bash", "example/suite/entrypoint.sh"]
