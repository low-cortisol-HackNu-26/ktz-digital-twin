# Celery application factory.
#
# celery_app = Celery("locomotive_twin")
#   broker: settings.CELERY_BROKER_URL  (Redis)
#   backend: settings.CELERY_RESULT_BACKEND  (Redis)
#   include: ["app.tasks.export", "app.tasks.alerts"]
#
# Config:
#   task_serializer: "json"
#   result_serializer: "json"
#   accept_content: ["json"]
#   timezone: "UTC"
#   task_track_started: True
#   task_soft_time_limit: 120   (seconds)
#   worker_prefetch_multiplier: 1  (one task at a time per worker)
