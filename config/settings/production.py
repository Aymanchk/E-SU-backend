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

# Хранилище файлов: S3 или MinIO
STORAGES = {  # noqa: F405
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET_NAME", default=""),  # noqa: F405
            "endpoint_url": env("S3_ENDPOINT_URL", default=""),  # noqa: F405
            "access_key": env("S3_ACCESS_KEY", default=""),  # noqa: F405
            "secret_key": env("S3_SECRET_KEY", default=""),  # noqa: F405
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
