from pathlib import Path
import os
import urllib.parse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-benchmark-test-key"

DEBUG = False

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # 'django.contrib.admin',
    # 'django.contrib.auth',
    "django.contrib.contenttypes",
    # 'django.contrib.sessions',
    # 'django.contrib.messages',
    "django.contrib.staticfiles",
    "benchmark",
]

MIDDLEWARE = [
    # 'django.middleware.security.SecurityMiddleware',
    # 'django.contrib.sessions.middleware.SessionMiddleware',
    "django.middleware.common.CommonMiddleware",
    # 'django.middleware.csrf.CsrfViewMiddleware',
    # 'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"

# Database Configuration
# Logic: Check DATABASE_URL, fallback to env vars DATABASE_URL_POOLED/DIRECT
db_url = os.getenv("DATABASE_URL")
if not db_url:
    if os.getenv("USE_CONNECTION_POOLING") == "1":
        db_url = os.getenv("DATABASE_URL_POOLED")
    else:
        db_url = os.getenv("DATABASE_URL_DIRECT")

if not db_url:
    # Fallback
    db_url = "postgresql://postgres:password@localhost:5432/benchmark_db"

# Parse DB URL
url = urllib.parse.urlparse(db_url)
path = url.path[1:]
user = url.username
password = url.password
host = url.hostname
port = url.port

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": path,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": int(os.getenv("CONN_MAX_AGE", 600)),
        "OPTIONS": {},
    }
}

# Disable prepared statements if using PgBouncer
if "pgbouncer" in db_url or os.getenv("USE_CONNECTION_POOLING") == "1":
    # For psycopg 3 (Django 5.0+)
    DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
