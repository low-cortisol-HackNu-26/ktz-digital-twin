# Celery tasks for alert evaluation and notification.
#
# @celery_app.task
# def evaluate_alerts(packet_json: dict) -> None
#   Called after each telemetry packet is ingested.
#   Steps:
#     1. Deserialize packet + current thresholds
#     2. For each parameter, check if value crosses into warning/critical range
#     3. If alert not already active: create AlertRecord in DB, publish to Redis
#        channel "alerts:{locomotiveId}" so WS clients receive it
#     4. If alert was active but value returned to normal: set resolved_at
#
# @celery_app.task
# def purge_old_alerts() -> None
#   Scheduled task (Celery beat): delete alerts older than 72h
#   Runs every hour
