# FastAPI application entry point.
#
# Setup:
#   - Create FastAPI(title="KTZ Digital Twin API", version="1.0.0")
#   - Include routers: auth, telemetry, history, alerts, export, health (all from api/routes/)
#   - Add CORS middleware (origins from settings.ALLOWED_ORIGINS)
#   - Add GZip middleware (min_size=1000) for REST responses
#   - Add request timing middleware (X-Process-Time header)
#   - On startup lifespan:
#       * Initialize DB connection pool (SQLAlchemy async engine)
#       * Load thresholds.json into memory (ThresholdsConfig singleton)
#       * Connect to Redis
#       * Register WebSocket manager
#   - On shutdown lifespan: close DB pool, Redis connection
#   - Mount /ws router (WebSocket endpoint)
#   - Swagger UI at /docs, ReDoc at /redoc
#
# Auth: all routes except GET /health and POST /api/auth/card require Bearer JWT.
