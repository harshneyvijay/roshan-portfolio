import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Minimal .env loader (no extra dependency)
_env = BASE_DIR / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is False.")
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
    ).split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]
# Render injects its public hostname; trust it automatically.
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}
# `manage.py test` never touches your real database: it uses SQLite unless TEST_DATABASE_URL is set.
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
_db_url = (
    os.environ.get("TEST_DATABASE_URL") if TESTING else os.environ.get("DATABASE_URL")
)
if _db_url:
    import dj_database_url

    # Neon suspends idle databases and drops open connections, so keep them short-lived and health-checked.
    DATABASES["default"] = dj_database_url.parse(
        _db_url,
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/cms/login/"
LOGIN_REDIRECT_URL = "/cms/"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
if os.environ.get("STORAGE_BACKEND", "local") == "s3":
    from botocore.config import Config

    STORAGES["default"] = {
        "BACKEND": "core.storage.ProxiedS3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME"),
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
            "region_name": os.environ.get("AWS_S3_REGION_NAME") or None,
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "custom_domain": os.environ.get("AWS_S3_CUSTOM_DOMAIN")
            or None,  # optional: public bucket / CDN host
            "addressing_style": os.environ.get("AWS_S3_ADDRESSING_STYLE", "path"),
            "signature_version": "s3v4",
            "querystring_auth": False,
            "file_overwrite": False,
            "default_acl": None,
            # Non-AWS S3 servers reject the newer default checksum headers.
            "client_config": Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                # Sign the body hash: some S3-compatible servers reject UNSIGNED-PAYLOAD.
                s3={
                    "payload_signing_enabled": True,
                    "addressing_style": os.environ.get(
                        "AWS_S3_ADDRESSING_STYLE", "path"
                    ),
                },
            ),
        },
    }

# Upload limits
MAX_IMAGE_MB = 8
MAX_PDF_MB = 20
DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# Security
X_FRAME_OPTIONS = (
    "SAMEORIGIN"  # required so same-site PDFs can render in <iframe>/<object>
)
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
