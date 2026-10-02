# The test runner image.
FROM python:3.12-slim

# The bytecode prefix keeps a mounted checkout's __pycache__ out of the way.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX=/tmp/pycache \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*
RUN cp -r /usr/share/novnc /opt/live \
    && printf '%s' '<!doctype html><meta charset="utf-8"><title>Live UI tests</title><meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=true&amp;view_only=true&amp;resize=scale&amp;reconnect=true">' > /opt/live/index.html

# Before the code, so a code change does not rebuild the browser.
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
