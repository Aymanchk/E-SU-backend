"""
Настройки для развёртывания на PythonAnywhere.

Оптимизированы для работы без внешних зависимостей (Redis, PostgreSQL, S3),
с полной и открытой поддержкой CORS для обращений с любого фронтенда и легким деплоем.
"""

from .base import *  # noqa: F401, F403

# Режим отладки: по умолчанию False, можно включить через .env (DEBUG=True)
DEBUG = env.bool("DEBUG", default=False)  # noqa: F405

# Разрешаем все хосты, чтобы приложение принимало запросы с любого домена/поддомена
ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# CORS & Безопасность (Полный доступ для любых внешних клиентов и браузеров)
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True
CORS_ORIGIN_ALLOW_ALL = True  # Для совместимости со старыми версиями django-cors-headers
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "*",
]

CORS_EXPOSE_HEADERS = ["*"]
CORS_PREFLIGHT_MAX_AGE = 86400

# Доверенные источники для CSRF (включая Vercel, PythonAnywhere и локальные порты)
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://*.pythonanywhere.com",
        "https://*.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
)

# Не принуждать к SSL-редиректу, чтобы работали и http://, и https:// запросы
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

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

# Локальное файловое хранилище
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
# DRF & Throttling (Отключаем ограничения по частоте запросов для публичного доступа)
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()  # Отключаем троттлинг для свободного доступа
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}

LOGGING["root"]["level"] = env("LOG_LEVEL", default="INFO")  # noqa: F405
