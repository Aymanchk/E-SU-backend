"""
Настройки для развёртывания на PythonAnywhere.

Оптимизированы для работы без внешних зависимостей (Redis, PostgreSQL, S3),
с полной поддержкой CORS для обращений с любого фронтенда и легким деплоем.
"""

from .base import *  # noqa: F401, F403

# Режим отладки: по умолчанию False, можно включить через .env (DEBUG=True)
DEBUG = env.bool("DEBUG", default=False)  # noqa: F405

# Разрешаем все хосты, чтобы приложение работало на любом домене:
# yourname.pythonanywhere.com, кастомных доменах или при прямых запросах
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])  # noqa: F405

# ---------------------------------------------------------------------------
# CORS & Безопасность
# ---------------------------------------------------------------------------

# Разрешаем запросы с любого frontend (localhost, Vercel, Netlify, Github Pages и т.д.)
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Доверенные источники для CSRF
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://*.pythonanywhere.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
)

# ---------------------------------------------------------------------------
# Celery & Фоновые задачи
# ---------------------------------------------------------------------------

# На PythonAnywhere задачи выполняются синхронно, не требуя отдельного Celery воркера
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# Кеш & Хранилище
# ---------------------------------------------------------------------------

# In-memory кеш (не требует Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "esu-pythonanywhere-cache",
    }
}

# Локальное файловое хранилище (если USE_S3=False)
if not env.bool("USE_S3", default=False):  # noqa: F405
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

# Если SMTP не настроен, письма логируются в консоль вместо ошибки
if not env("EMAIL_HOST", default=""):  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ---------------------------------------------------------------------------
# DRF & Throttling
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "login": "300/min",
    "password_reset": "100/hour",
}

LOGGING["root"]["level"] = env("LOG_LEVEL", default="INFO")  # noqa: F405
