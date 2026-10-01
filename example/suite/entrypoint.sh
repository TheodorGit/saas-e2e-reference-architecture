#!/usr/bin/env bash
# The test runner's entry point.
#
# By default the browser runs headed on a virtual screen, slowed down so a person
# can follow it, and that screen is viewable at http://localhost:7900. With
# E2E_HEADLESS=1 (CI) it runs headless at full speed. Either way, a notice says
# at the start and at the end where the report and the videos are.
set -u
VIEW_PORT="${E2E_VIEW_PORT:-7900}"
SLOWMO_MS="${E2E_SLOWMO_MS:-300}"
PYTEST_ARGS=(example/suite -p no:cacheprovider)

notice() {
  # A box as wide as its longest line (at least 72), so no line breaks the border.
  local line bar width=72
  for line in "$@"; do [ ${#line} -gt "$width" ] && width=${#line}; done
  bar=$(printf '%*s' $((width + 4)) '' | tr ' ' '-')
  echo "+${bar}+"
  for line in "$@"; do printf '|  %-*s  |\n' "$width" "$line"; done
  echo "+${bar}+"
}

wait_for_port() {
  # Poll until the port accepts a connection (10 s budget).
  python - "$1" <<'PY'
import socket, sys, time
port, deadline = int(sys.argv[1]), time.monotonic() + 10
while time.monotonic() < deadline:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.2)  # bounded poll: the server is still starting
sys.exit(1)
PY
}

start_live_view() {
  # A restarted runner keeps /tmp: a lock left by an interrupted run would stop
  # the virtual screen from starting, so clear it first.
  rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
  export DISPLAY=:99
  Xvfb :99 -screen 0 1440x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 -quiet \
         -o /tmp/x11vnc.log >/dev/null 2>&1 &
  wait_for_port 5900 || return 1
  websockify --web /opt/live "$VIEW_PORT" localhost:5900 >/tmp/websockify.log 2>&1 &
  wait_for_port "$VIEW_PORT" || return 1
}

where=("  the report:  reports/latest.html"
       "  the videos:  one per browser test, linked from the report")
if [ "${E2E_HEADLESS:-0}" = "1" ]; then
  notice "Running headless (E2E_HEADLESS=1). When the run ends you will find:" "${where[@]}"
elif start_live_view; then
  notice "Watch the UI tests live:  http://localhost:${VIEW_PORT}" \
         "Or don't. When the run ends you will find:" "${where[@]}"
  PYTEST_ARGS+=(--headed --slowmo "$SLOWMO_MS")
else
  # Better a headless run with results than every browser test failing.
  unset DISPLAY
  notice "The live view could not start, so this run is headless" \
         "(details: /tmp/xvfb.log, /tmp/x11vnc.log, /tmp/websockify.log in the runner)." \
         "When the run ends you will find:" "${where[@]}"
fi

python -m pytest "${PYTEST_ARGS[@]}"
code=$?

run=$(sed -n 's/.*url=\([^"]*\)\/report\.html.*/\1/p' reports/latest.html 2>/dev/null | head -1)
if [ "$code" = "0" ]; then verdict="PASSED"; else verdict="FAILED (pytest exit code $code)"; fi
notice "Run finished: ${verdict}" \
       "  the report:  reports/latest.html   (this run: reports/${run:-?}/report.html)" \
       "  the videos:  reports/${run:-?}/videos/  - one per browser test"
exit "$code"
