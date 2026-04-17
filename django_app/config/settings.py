import os
from pathlib import Path
import yaml
import dj_database_url

from dotenv import load_dotenv
load_dotenv()  # Explicitly load the .env file

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "call-power-django-dev-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if host]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
USE_NGROK = os.environ.get("USE_NGROK", "False") == "True" and os.environ.get("RUN_MAIN", None) != "true"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "callpower.apps.core",
    "callpower.apps.api",
    "callpower.apps.auth",
    "callpower.apps.calls",
    "callpower.apps.political_data",
    "callpower.apps.public",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

default_db = os.environ.get("DATABASE_URI") or os.environ.get("DATABASE_URL")
if default_db:
    DATABASES = {
        "default": dj_database_url.parse(default_db, conn_max_age=600),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": REPO_DIR / "dev.db",
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOGIN_URL = "/user/login/"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static", REPO_DIR / "call_server" / "static"]
STATIC_ROOT = REPO_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = REPO_DIR / "instance" / "uploads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

AUTHENTICATION_BACKENDS = [
    "callpower.auth_backends.LegacyUserBackend",
]

REACT_DEV_SERVER_URL = os.environ.get("REACT_DEV_SERVER_URL", "http://localhost:5173")
INSTALLED_ORG = os.environ.get("INSTALLED_ORG", "OpenSourceActivism.tech")
SITENAME = os.environ.get("SITENAME", "Call Power")
SENTRY_DSN_PUBLIC_KEY = os.environ.get("SENTRY_DSN_PUBLIC_KEY", "")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
if not TWILIO_ACCOUNT_SID:
    print("Warning: TWILIO_ACCOUNT_SID not set, Twilio integration will not work")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_TIME_LIMIT = int(os.environ.get("TWILIO_TIME_LIMIT", 60 * 60))
TWILIO_TIMEOUT = int(os.environ.get("TWILIO_TIMEOUT", 60))
LOG_PHONE_NUMBERS = os.environ.get("LOG_PHONE_NUMBERS", "true").lower() in {"1", "true", "yes", "on"}

CRM_INTEGRATION = os.environ.get("CRM_INTEGRATION", "")
CRM_DEBUG_PHONE = os.environ.get("CRM_DEBUG_PHONE", "+15555550199")
ACTIONKIT_DOMAIN = os.environ.get("ACTIONKIT_DOMAIN")
ACTIONKIT_USER = os.environ.get("ACTIONKIT_USER")
ACTIONKIT_PASSWORD = os.environ.get("ACTIONKIT_PASSWORD")
ACTIONKIT_API_KEY = os.environ.get("ACTIONKIT_API_KEY")
ROGUE_DOMAIN = os.environ.get("ROGUE_DOMAIN")
ROGUE_API_KEY = os.environ.get("ROGUE_API_KEY")
MOBILE_COMMONS_USERNAME = os.environ.get("MOBILE_COMMONS_USERNAME")
MOBILE_COMMONS_PASSWORD = os.environ.get("MOBILE_COMMONS_PASSWORD")
MOBILE_COMMONS_COMPANY = os.environ.get("MOBILE_COMMONS_COMPANY")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 25))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"no-reply@{INSTALLED_ORG.lower()}")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", DEFAULT_FROM_EMAIL)

CAMPAIGN_MESSAGE_DEFAULTS = yaml.safe_load((REPO_DIR / "instance" / "campaign_msg_defaults.yaml").read_text())

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "call-power-django",
        "OPTIONS": {
            "MAX_ENTRIES": 100000,
        },
    }
}
