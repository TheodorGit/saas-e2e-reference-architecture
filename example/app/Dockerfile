# Demo ESP App: the web app and its worker share this image (different commands).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEMO_ESP_DB=/data/demo-esp.sqlite3
WORKDIR /srv

COPY example/app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY example/__init__.py example/__init__.py
COPY example/app example/app

EXPOSE 8000
CMD ["uvicorn", "example.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
