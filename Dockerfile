# Treasury Ledger — Fly.io deployment image.
#
# Needs a real system package (tesseract-ocr) for the OCR fallback path in
# app/pdf_processing.py -- pytesseract shells out to the `tesseract` binary,
# it isn't a pure Python package, so this can't be a "just pip install"
# image. This is exactly the reason a platform like Vercel's standard Python
# runtime doesn't work for this app: it only supports pip installs, no apt
# step. A plain Docker image, which is what Fly.io (and Railway/Render) run,
# doesn't have that limitation.
FROM python:3.11-slim

# tesseract-ocr: the OCR engine itself (app/pdf_processing.py's OCR fallback).
# libgl1: a common transitive requirement for Pillow/image libs on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/

# The SQLite database file lives on a Fly Volume mounted at /data (see
# fly.toml's [[mounts]] and DEPLOY.md) so it survives deploys and restarts.
# Point the app at it via the same TREASURY_LEDGER_DB env var the test suite
# already uses to redirect the database elsewhere.
ENV TREASURY_LEDGER_DB=/data/treasury_ledger.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
