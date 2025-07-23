import importlib
import json
import os
import sys
from unittest.mock import patch


@patch.dict(
    os.environ,
    {
        "MPT_API_BASE_URL": "https://api.example.com",
        "MPT_API_TOKEN": "test-token",
        "MPT_PRODUCTS_IDS": "123,456",
        "MPT_PORTAL_BASE_URL": "https://portal.example.com",
        "MPT_KEY_VAULT_NAME": "test-keyvault",
        "MPT_NOTIFY_CATEGORIES": json.dumps(["category1", "category2"]),
        "MPT_ORDERS_API_POLLING_INTERVAL_SECS": "120",
        "MPT_INITIALIZER": "custom.initializer",
    },
)
def test_settings_values(settings):
    settings = importlib.reload(importlib.import_module("tests.django.settings"))

    assert settings.SECRET_KEY == os.environ.get("DJANGO_SECRET", "secret_key")
    assert settings.SERVICE_NAME == os.getenv("SERVICE_NAME", "Swo.Extensions.AWS")
    assert settings.USE_APPLICATIONINSIGHTS == (
        os.getenv("USE_APPLICATIONINSIGHTS", "False").lower() in ("true", "1", "t")
    )
    assert settings.MPT_API_BASE_URL == "https://api.example.com"
    assert settings.MPT_API_TOKEN == "test-token"
    assert (
        settings.MPT_PRODUCTS_IDS == ["PRD-1111-1111"]
        or settings.MPT_PRODUCTS_IDS == "[PRD-1111-1111]"
    )
    assert settings.MPT_PORTAL_BASE_URL == "https://portal.s1.local"
    assert settings.MPT_KEY_VAULT_NAME == "test-keyvault"
    assert settings.EXTENSION_CONFIG["DUE_DATE_DAYS"] == "30"
    assert settings.MPT_ORDERS_API_POLLING_INTERVAL_SECS == 30
    assert (
        settings.MPT_SETUP_CONTEXTS_FUNC == "mpt_extension_sdk.runtime.events.utils.setup_contexts"
    )
    assert settings.INITIALIZER == "custom.initializer"
    assert settings.MPT_NOTIFY_CATEGORIES == ["category1", "category2"]


def test_debug_and_allowed_hosts(settings):
    assert settings.DEBUG is False
    assert settings.ALLOWED_HOSTS == ["*", "testserver"]


def test_logging_config(settings):
    assert "handlers" in settings.LOGGING
    assert "console" in settings.LOGGING["handlers"]
    assert settings.LOGGING["root"]["handlers"] == ["console"]


def test_opentelemetry_setup(monkeypatch, mock_app_insights_instrumentation_key):
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", mock_app_insights_instrumentation_key
    )
    monkeypatch.setenv("USE_APPLICATIONINSIGHTS", "True")

    sys.modules.pop("swo_runtime.default", None)

    import swo_runtime.default

    importlib.reload(swo_runtime.default)

    assert swo_runtime.default.USE_APPLICATIONINSIGHTS is True
    assert swo_runtime.default.APPLICATIONINSIGHTS_CONNECTION_STRING == (
        mock_app_insights_instrumentation_key
    )
