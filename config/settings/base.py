"""
Базовые настройки проекта E-SU.
Общие для всех окружений. Переопределяются в development.py и production.py.
"""

from datetime import timedelta
from pathlib import Path

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

try:
    import environ

    env = environ.Env(
        DEBUG=(bool, False),
    )
    environ.Env.read_env(BASE_DIR / ".env")
except ImportError:
    import os

    class _FallbackEnv:
        def __init__(self, **defaults):
            self.defaults = defaults

        def __call__(self, key, default=None):
            return os.environ.get(key, default)

        def bool(self, key, default=False):
            val = os.environ.get(key)
            if val is None:
                return default
            return str(val).lower() in ("true", "1", "yes", "on")

        def int(self, key, default=0):
            val = os.environ.get(key)
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def list(self, key, default=None):
            val = os.environ.get(key)
            if val is None:
                return default if default is not None else []
            return [x.strip() for x in val.split(",") if x.strip()]

        def db(self, key, default=None):
            val = os.environ.get(key, default)
            if not val or "sqlite" in val:
                path = val.replace("sqlite:///", "").replace("sqlite://", "") if val else str(BASE_DIR / "db.sqlite3")
                return {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": path,
                }
            return {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(BASE_DIR / "db.sqlite3"),
            }

        @staticmethod
        def read_env(*args, **kwargs):
            pass

    env = _FallbackEnv()


# ---------------------------------------------------------------------------
# Основное
# ---------------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY", default="django-insecure-e-su-secret-key-change-in-production-2026")
DEBUG = env("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# Версия API. Основные эндпоинты подключаются под /api/${API_VERSION}/.
API_VERSION = env("API_VERSION", default="v1")


# ---------------------------------------------------------------------------
# Приложения
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "storages",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.audit",
    "apps.documents",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# База данных
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = 60


# ---------------------------------------------------------------------------
# Пользователи и пароли
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # 24 часа


# ---------------------------------------------------------------------------
# Локализация
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Asia/Bishkek"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Статика и медиа
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Хранилище файлов. В development локальное, в production S3/MinIO.
if env.bool("USE_S3", default=False):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": env("S3_BUCKET_NAME", default="esu-documents"),
                "endpoint_url": env("S3_ENDPOINT_URL", default=""),
                "access_key": env("S3_ACCESS_KEY", default=""),
                "secret_key": env("S3_SECRET_KEY", default=""),
                "region_name": env("S3_REGION_NAME", default="us-east-1"),
                "default_acl": None,
                "querystring_auth": True,
                "file_overwrite": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

MAX_DOCUMENT_FILE_SIZE = env.int("MAX_DOCUMENT_FILE_SIZE", default=20 * 1024 * 1024)
MAX_DOCUMENT_FILES = env.int("MAX_DOCUMENT_FILES", default=10)
DOCUMENT_NUMBER_FORMAT = env(
    "DOCUMENT_NUMBER_FORMAT", default="{prefix}-{department}-{year}-{number}"
)
DOCUMENT_NUMBER_PREFIX = env("DOCUMENT_NUMBER_PREFIX", default="ESU")
DOCUMENT_NUMBER_PADDING = env.int("DOCUMENT_NUMBER_PADDING", default=6)
NOTIFICATION_EMAIL_ENABLED = env.bool("NOTIFICATION_EMAIL_ENABLED", default=False)
DEADLINE_APPROACHING_DAYS = env.int("DEADLINE_APPROACHING_DAYS", default=1)
NOTIFICATION_RETENTION_DAYS = env.int("NOTIFICATION_RETENTION_DAYS", default=90)


# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("apps.common.renderers.EnvelopeJSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "password_reset": "5/hour",
    },
}


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("ACCESS_TOKEN_LIFETIME_MINUTES", default=30)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("REFRESH_TOKEN_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
}


# ---------------------------------------------------------------------------
# Документация API
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "E-SU API",
    "DESCRIPTION": "Electronic Salymbekov University. Backend API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": f"/api/{API_VERSION}",
    "SORT_OPERATIONS": False,
    # Показывать в схеме только версионированные пути, legacy /api/ исключаем.
    "PREPROCESSING_HOOKS": ["apps.common.schema.exclude_legacy_paths"],
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayOperationId": False,
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.common.schema.envelope_postprocessing_hook",
    ],
    "ENUM_NAME_OVERRIDES": {
        "UserStatusEnum": "apps.accounts.models.UserStatus",
        "DepartmentStatusEnum": "apps.organizations.models.DepartmentStatus",
        "DocumentCategoryStatusEnum": "apps.documents.models.DocumentCategoryStatus",
        "DocumentStatusEnum": "apps.documents.models.DocumentStatus",
        "DocumentPriorityEnum": "apps.documents.models.DocumentPriority",
        "ApprovalRouteStatusEnum": "apps.documents.models.ApprovalRouteStatus",
        "ApprovalStepStatusEnum": "apps.documents.models.ApprovalStepStatus",
        "ApprovalActionTypeEnum": "apps.documents.models.ApprovalActionType",
        "DocumentCommentTypeEnum": "apps.documents.models.DocumentCommentType",
        "DocumentHistoryActionEnum": "apps.documents.models.DocumentHistoryAction",
        "NotificationTypeEnum": "apps.notifications.models.NotificationType",
    },
    "TAGS": [
        {"name": "Auth", "description": "Авторизация и профиль"},
        {"name": "Users", "description": "Пользователи"},
        {"name": "Roles", "description": "Роли и права"},
        {"name": "Departments", "description": "Подразделения"},
        {"name": "Audit", "description": "Журнал аудита"},
        {"name": "Settings", "description": "Системные настройки"},
        {"name": "System", "description": "Служебные эндпоинты"},
    ],
}


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
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

CSRF_TRUSTED_ORIGINS = env.list(
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


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", default="")
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=not bool(REDIS_URL))
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_BEAT_SCHEDULE = {
    "check-upcoming-document-deadlines": {
        "task": "apps.notifications.tasks.check_upcoming_document_deadlines",
        "schedule": 1800.0,
    },
    "mark-overdue-documents": {
        "task": "apps.notifications.tasks.mark_overdue_documents",
        "schedule": 1800.0,
    },
    "cleanup-old-notifications": {
        "task": "apps.notifications.tasks.cleanup_old_notifications",
        "schedule": 86400.0,
    },
}


# ---------------------------------------------------------------------------
# Кеш (используется для системных настроек, apps/common/settings_service.py)
# ---------------------------------------------------------------------------

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "esu-default-cache",
        }
    }


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@esu.kg")

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
FRONTEND_RESET_PASSWORD_URL = env(
    "FRONTEND_RESET_PASSWORD_URL",
    default="http://localhost:3000/reset-password",
)


# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
