# Multi-stage Dockerfile for FastAPI backend.
#
# Stage 1 — builder:
#   FROM python:3.12-slim
#   Install build tools, copy requirements.txt, pip install --no-cache-dir
#
# Stage 2 — runtime:
#   FROM python:3.12-slim
#   Copy installed packages from builder (reduces image size)
#   Copy app/ directory
#   Expose port 8000
#   Healthcheck: GET /health every 30s
#   CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
#
# Non-root user: create appuser, chown /app
