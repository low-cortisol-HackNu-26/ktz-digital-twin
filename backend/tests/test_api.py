# Integration tests for REST API routes.
# Uses httpx.AsyncClient with app fixture.
#
# test_health_endpoint_returns_ok:
#   GET /health → 200, body.status == "ok"
#
# test_get_thresholds:
#   GET /api/thresholds with valid token → 200, valid ThresholdsConfig JSON
#
# test_update_thresholds_requires_admin:
#   PUT /api/thresholds with Dispatcher token → 403
#   PUT /api/thresholds with Admin token → 200
#
# test_history_returns_packets_in_range:
#   Seed DB with 10 packets, GET /api/history?from=...&to=... → correct subset
#
# test_export_pdf_job_lifecycle:
#   POST /api/export → 202 with jobId
#   GET /api/export/{jobId} → eventually status "done"
#   GET /api/export/{jobId}/file → 200 with Content-Type application/pdf
