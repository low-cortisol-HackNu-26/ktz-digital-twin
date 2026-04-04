# ktz-digital-twin

# README content to include:
#
# ## Overview
#   One-paragraph description: real-time locomotive telemetry dashboard with health index.
#
# ## Architecture diagram
#   ASCII or linked image showing: Simulator → Backend (FastAPI + Redis) → Frontend (Next.js)
#   Keycloak for auth, TimescaleDB for history, Nginx as gateway.
#
# ## Quick start
#   git clone ...
#   cp .env.example .env   # fill secrets
#   docker compose up --build
#
# ## Service URLs (after boot)
#   Dashboard:      http://localhost:3000
#   Swagger UI:     http://localhost:8000/docs
#   Keycloak Admin: http://localhost:8080  (admin / from .env)
#   WebSocket:      ws://localhost/ws/telemetry/{locomotiveId}
#
# ## Health Index formula
#   Explain weights, normalization, penalty logic (reference shared/thresholds.json)
#
# ## Simulator scenarios
#   normal, anomaly, highload (10x Hz) — how to switch
#
# ## Running tests
#   cd backend && pytest
#
# ## Export
#   PDF/CSV report via GET /api/export?from=&to=&format=pdf|csv
