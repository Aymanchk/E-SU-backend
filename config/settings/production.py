"""Настройки для production."""

from .base import *  # noqa: F401,F403

DEBUG = False

# Обязательно задать реальные хосты через переменную окружения
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Безопасность
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# В production USE_S3=True обязателен; параметры S3/MinIO читаются в base.py.
if not env.bool("USE_S3", default=False):  # noqa: F405
    raise ValueError("В production необходимо установить USE_S3=True")

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
}

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
