# REST routes for report export (async via Celery).
#
# POST /api/export
#   Body: { locomotiveId, from, to, format: "pdf" | "csv", includeAlerts: bool }
#   Auth: any authenticated user
#   Enqueues Celery task (tasks/export.py) and returns { jobId: str }
#
# GET /api/export/{jobId}
#   Returns: { status: "pending"|"running"|"done"|"failed", url?: str }
#   On done: url is a signed download URL (or /api/export/{jobId}/file)
#
# GET /api/export/{jobId}/file
#   Streams the generated PDF or CSV file as a download response
#   Sets Content-Disposition: attachment; filename="report_{locomotiveId}_{from}_{to}.{ext}"
