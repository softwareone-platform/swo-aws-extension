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
    settings = importlib.reload(importlib.import_module("swo_aws_extension.default"))

    assert os.environ.get("DJANGO_SECRET", "django_secret") == settings.SECRET_KEY
    assert os.getenv("SERVICE_NAME", "Swo.Extensions.SwoDefaultExtensions") == settings.SERVICE_NAME
    assert (
        os.getenv("USE_APPLICATIONINSIGHTS", "False").lower() in {"true", "1", "t"}
    ) == settings.USE_APPLICATIONINSIGHTS
    assert settings.MPT_API_BASE_URL == "https://api.example.com"
    assert settings.MPT_API_TOKEN == "test-token"
    assert settings.MPT_PRODUCTS_IDS == "123,456"
    assert settings.MPT_PORTAL_BASE_URL == "https://portal.example.com"
    assert settings.MPT_KEY_VAULT_NAME == "test-keyvault"
    assert settings.EXTENSION_CONFIG["DUE_DATE_DAYS"] == "30"
    assert settings.MPT_ORDERS_API_POLLING_INTERVAL_SECS == 120
    assert settings.MPT_SETUP_CONTEXTS_FUNC == (
        "swo_aws_extension.flows.fulfillment.base.setup_contexts"
    )
    assert settings.INITIALIZER == "custom.initializer"
    assert settings.MPT_NOTIFY_CATEGORIES == ["category1", "category2"]
    assert settings.DEBUG is True
    assert settings.ALLOWED_HOSTS == ["*"]
    assert "handlers" in settings.LOGGING
    assert "console" in settings.LOGGING["handlers"]
    assert settings.LOGGING["root"]["handlers"] == ["rich"]


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
def test_settings_values_with_app_insights(
    mocker, monkeypatch, mock_app_insights_connection_string
):
    sys.modules.pop("swo_aws_extension.default", None)

    mocker.patch("swo_aws_extension.default.set_logger_provider")
    mocker.patch("swo_aws_extension.default.LoggerProvider")
    mocker.patch("swo_aws_extension.default.AzureMonitorLogExporter")
    mocker.patch("swo_aws_extension.default.BatchLogRecordProcessor")

    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", mock_app_insights_connection_string)

    settings = importlib.reload(importlib.import_module("swo_aws_extension.default"))

    assert settings.USE_APPLICATIONINSIGHTS is True
    assert mock_app_insights_connection_string == settings.APPLICATIONINSIGHTS_CONNECTION_STRING
