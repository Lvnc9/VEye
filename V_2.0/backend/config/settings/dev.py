from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Permissive dev CORS/CSRF in addition to whatever's in the env.
CORS_ALLOWED_ORIGINS = list(set(CORS_ALLOWED_ORIGINS + ["http://localhost:3000", "http://127.0.0.1:3000"]))
CSRF_TRUSTED_ORIGINS = list(set(CSRF_TRUSTED_ORIGINS + ["http://localhost:3000", "http://127.0.0.1:3000"]))

JWT_COOKIE_SECURE = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
