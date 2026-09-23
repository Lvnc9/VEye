"""
Base Django settings for VEye V2, shared by dev.py and prod.py.

Env strategy: values come from environment variables (docker-compose.yml sets
these in the `backend` service), read via django-environ. A local
`backend/.env` (gitignored) can also be used; see `backend/.env.example`.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    JWT_COOKIE_SECURE=(bool, False),
)

# Reads backend/.env if present; harmless no-op if it doesn't exist (e.g. in
# docker-compose, where env vars are injected directly).
environ.Env.read_env(str(BASE_DIR / ".env"))

# The fallback is dev-only and deliberately >= 32 bytes: it doubles as the
# SIMPLE_JWT signing key, and PyJWT warns on HS256 keys shorter than that.
# Production supplies DJANGO_SECRET_KEY via .env; prod.py refuses to start
# without it.
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="insecure-dev-key-change-me-before-deploying-anywhere",
)

DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_ratelimit",
    # Local apps
    "apps.core",
    "apps.accounts",
    "apps.organization",
    "apps.projects",
    "apps.chat",
    "apps.documents",
    "apps.dashboard",
    "apps.pdfgen",
    "apps.importer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Django's CsrfViewMiddleware stays enabled globally (see apps/accounts
    # for exactly how CSRF is enforced on cookie-authenticated JWT views —
    # short version: csrf_protect is applied explicitly on mutating auth/API
    # views rather than relying on SessionAuthentication).
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://veye:veye@localhost:5432/veye",
    )
}

# ---------------------------------------------------------------------------
# Cache (Redis via django-redis) — also backs the JWT refresh-token blacklist
# and the dashboard metrics cache (see apps/accounts/authentication.py and
# apps/dashboard/views.py).
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fa"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="Asia/Tehran")
USE_I18N = True
USE_TZ = True

# Document dates are Jalali throughout the domain (V_1.0 formats them
# "%Y/%m/%d" via jdatetime, e.g. "1404/01/19"). Timestamps stay as real
# timezone-aware datetimes; Jalali is a presentation concern.
JALALI_DATE_FORMAT = "%Y/%m/%d"

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Uploads. A designer save is one JSON body (the whole document), which can be
# larger than Django's 2.5 MB default for non-file request data; files themselves
# are streamed to disk and only limited by the caps below.
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10 * 1024 * 1024)
DOCUMENT_FILE_MAX_BYTES = env.int("DOCUMENT_FILE_MAX_BYTES", default=100 * 1024 * 1024)
LOGO_MAX_BYTES = env.int("LOGO_MAX_BYTES", default=5 * 1024 * 1024)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    # django-filter is intentionally not a dependency; ViewSets filter
    # manually in get_queryset() from query params instead (see apps/documents/views.py).
    "EXCEPTION_HANDLER": "apps.core.exceptions.veye_exception_handler",
}

# ---------------------------------------------------------------------------
# SimpleJWT
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_TOKEN_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_TOKEN_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,  # we roll our own Redis-backed blacklist, see apps/accounts
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "USER_ID_FIELD": "national_code",
    "USER_ID_CLAIM": "national_code",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Cookie names/flags for the JWT-in-httpOnly-cookie auth scheme (apps/accounts).
JWT_ACCESS_COOKIE_NAME = "access_token"
JWT_REFRESH_COOKIE_NAME = "refresh_token"
JWT_CSRF_COOKIE_NAME = "csrftoken"
JWT_COOKIE_SECURE = env.bool("JWT_COOKIE_SECURE", default=False)
JWT_COOKIE_SAMESITE = env("JWT_COOKIE_SAMESITE", default="Lax")
JWT_COOKIE_PATH = "/"

# Frontend base URL used to build the public QR-validation link
# (`/validate/<qr_token>`); the frontend hosts that route (see skeleton.md §2).
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")

# ---------------------------------------------------------------------------
# CORS / CSRF (cross-origin cookie-based auth: Next.js -> Django)
# ---------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"])

CSRF_COOKIE_NAME = JWT_CSRF_COOKIE_NAME
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
CSRF_COOKIE_HTTPONLY = False  # must be readable by frontend JS to echo back in X-CSRFToken

# ---------------------------------------------------------------------------
# Login rate limiting (django-ratelimit + django-redis) — replaces V1's toy
# arithmetic CAPTCHA (skeleton.md §8.7).
# ---------------------------------------------------------------------------
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = True
LOGIN_RATELIMIT_RATE = env("LOGIN_RATELIMIT_RATE", default="10/m")
# The public /verify/ lookup (what a scanned QR code opens). Unauthenticated, so
# it is limited per IP; a person scanning a stack of printed documents stays far below this.
VERIFY_RATELIMIT_RATE = env("VERIFY_RATELIMIT_RATE", default="60/m")

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
# Keep retrying the broker connection at startup (Celery 6 changes the
# default); the worker can come up before Redis is reachable.
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# PDF rendering is CPU-bound and can take seconds on a long document; a hard
# ceiling keeps one bad document from pinning a worker forever.
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=300)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=270)

# ---------------------------------------------------------------------------
# PDF engine (apps.pdfgen, Phase 4)
# ---------------------------------------------------------------------------
# Absolute paths — the original renderer resolved fonts as bare "./Vazir.ttf"
# against the process CWD, and two *different* Vazir builds exist in V_1.0
# (repo root vs other_folder/, differing md5 and size). These are the repo-root
# pair, which is what production actually loaded.
PDF_FONT_DIR = BASE_DIR / "assets" / "fonts"
PDF_FONT_REGULAR = PDF_FONT_DIR / "Vazir.ttf"
PDF_FONT_BOLD = PDF_FONT_DIR / "Vazir-Bold.ttf"
PDF_FONT_NAME = "Vazir"

# چاپ لیست (bulk print): the most PDFs one ZIP download may hold. Bulk print only
# packs files that already exist, so this bounds response size, not render time.
BULK_PRINT_MAX_FILES = env.int("BULK_PRINT_MAX_FILES", default=200)

# First-run setup (docs/11 §4). The one-time token that lets the first مدیر عامل be created on
# a fresh database, sent as the X-VEYE-Setup-Token header. Unset or empty = the setup endpoint
# answers 503 as if it did not exist, so a deployment that forgot to set it cannot be
# bootstrapped by a stranger. Delete it from .env once setup is done. prod.py insists on 32+ bytes.
SETUP_TOKEN = env("VEYE_SETUP_TOKEN", default="")
SETUP_RATELIMIT_RATE = env("SETUP_RATELIMIT_RATE", default="5/m")

# Organisation chart: the most nodes GET /org/tree/ returns in one response. Over
# it the endpoint returns only the top two levels plus `"truncated": true`, and the
# client fetches the rest a branch at a time with `?parent=<id>`.
ORG_TREE_MAX_NODES = env.int("ORG_TREE_MAX_NODES", default=2000)

# Projects (docs/11 §2.4): how many people may be on one project. Objectives per project
# (PROJECT_MAX_OBJECTIVES, slice 8.2) is bounded the same way, mirroring `revision_limit`.
PROJECT_MAX_MEMBERS = env.int("PROJECT_MAX_MEMBERS", default=100)
PROJECT_MAX_OBJECTIVES = env.int("PROJECT_MAX_OBJECTIVES", default=200)

# Chat (Phase 9): per-user limit on opening DMs (a rate-limited request is a 403, like login/verify).
CHAT_OPEN_DIRECT_RATELIMIT_RATE = env("CHAT_OPEN_DIRECT_RATELIMIT_RATE", default="30/m")
CHAT_SEND_RATELIMIT_RATE = env("CHAT_SEND_RATELIMIT_RATE", default="60/m")
CHAT_PAGE_SIZE = env.int("CHAT_PAGE_SIZE", default=50)
CHAT_MAX_PAGE_SIZE = env.int("CHAT_MAX_PAGE_SIZE", default=200)
