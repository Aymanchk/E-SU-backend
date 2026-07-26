import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("esu")

# namespace="CELERY" означает, что Celery берёт из settings
# все переменные, начинающиеся на CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Ищет tasks.py во всех приложениях из INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
