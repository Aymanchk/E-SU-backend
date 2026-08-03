"""Настройки для локальной разработки."""

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Письма печатаются в консоль вместо реальной отправки
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Разрешаем любой источник, чтобы не мучиться с фронтом локально
CORS_ALLOW_ALL_ORIGINS = True

# Celery выполняет задачи сразу, без воркера.
# Полезно, когда не хотите держать запущенный worker.
# Для проверки реальной работы Celery поставь False.
CELERY_TASK_ALWAYS_EAGER = False

# Отключаем троттлинг, чтобы не мешал при отладке
REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "login": "1000/min",
    "password_reset": "1000/hour",
}
