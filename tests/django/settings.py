"""
Django settings for pippo project.

Generated by 'django-admin startproject' using Django 4.2.8.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET", "secret_key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "swo.mpt.extensions.runtime.djapp.apps.DjAppConfig",
    "swo_aws_extension.apps.ExtensionConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "swo.mpt.extensions.runtime.djapp.middleware.MPTClientMiddleware",
]

ROOT_URLCONF = "swo.mpt.extensions.runtime.djapp.conf.urls"

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


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
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
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "swo.mpt.extensions.runtime": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Proxy settings
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# OpenTelemetry configuration
SERVICE_NAME = os.getenv("SERVICE_NAME", "Swo.Extensions.AWS")
USE_APPLICATIONINSIGHTS = os.getenv("USE_APPLICATIONINSIGHTS", "False").lower() in (
    "true",
    "1",
    "t",
)
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv(
    "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
)

MPT_API_BASE_URL = os.getenv("MPT_API_BASE_URL", "http://localhost:8000")
MPT_API_TOKEN = os.getenv("MPT_API_TOKEN", "change-me!")
MPT_API_TOKEN_OPERATIONS = os.getenv("MPT_API_TOKEN_OPERATIONS", "change-me!")
MPT_PRODUCTS_IDS = ["PRD-1111-1111"]
MPT_ORDERS_API_POLLING_INTERVAL_SECS = 30
MPT_PORTAL_BASE_URL = "https://portal.s1.local"

EXTENSION_CONFIG = {
    "WEBHOOKS_SECRETS": {"PRD-1111-1111": "that's my awesome test secret"},
    "MAX_RETRY_ATTEMPS": "10",
    "DUE_DATE_DAYS": "30",
    "CCP_CLIENT_ID": "client_id",
    "CCP_CLIENT_SECRET": "client_secret",
    "AWS_OPENID_SCOPE": "scope",
    "CCP_OAUTH_URL": "https://ccpoauth.com/oauth2/token",
    "AWS_REGION": "us-east-1",
    "AIRTABLE_API_TOKEN": "api_key",
    "AIRTABLE_BASES": "base_id",
}
MPT_SETUP_CONTEXTS_FUNC = "swo.mpt.extensions.runtime.events.utils.setup_contexts"
