# Celery task for generating PDF and CSV reports.
#
# @celery_app.task(bind=True)
# def generate_export(self, job_id: str, locomotive_id: str, from_ts: int, to_ts: int,
#                     format: str, include_alerts: bool) -> str
#
# Steps:
#   1. Query TelemetryRecord rows for the time window from DB
#   2. Query AlertRecord rows if include_alerts=True
#   3. If format == "csv":
#      - Convert to pandas DataFrame
#      - Export to CSV bytes
#   4. If format == "pdf":
#      - Use reportlab or weasyprint to render:
#          * Cover page: locomotive ID, time range, health summary
#          * Table of statistics (min/max/avg per parameter)
#          * Chart screenshots (or ASCII-art if no headless browser)
#          * Alert log table
#   5. Write output file to /tmp/exports/{job_id}.{ext}
#   6. Update job status in Redis: SET export:{job_id} {"status":"done","path":...}
#
# On failure: set status="failed" in Redis
