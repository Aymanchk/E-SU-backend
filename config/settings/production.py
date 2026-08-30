"""Настройки для production."""

from .base import *  # noqa: F401,F403

DEBUG = False

# Обязательно задать реальные хосты через переменную окружения или "*"
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if env("EMAIL_HOST", default="") else "django.core.mail.backends.console.EmailBackend"  # noqa: F405

# Безопасность
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)  # noqa: F405
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not env.bool("USE_S3", default=False):  # noqa: F405
    STORAGES = {  # noqa: F405
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES["staticfiles"] = {  # noqa: F405
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    }

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
