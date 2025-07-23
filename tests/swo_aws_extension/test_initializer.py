import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def clear_initializer_env(monkeypatch):
    monkeypatch.delenv("MPT_INITIALIZER", raising=False)


def make_mock_settings(app_config_name, use_app_insights=False, handler="console"):
    """
    Create a mock settings object for testing purposes to correct test instability
    behavior.
    """

    class MockSettings:
        USE_APPLICATIONINSIGHTS = use_app_insights
        DEBUG = False
        INSTALLED_APPS = []
        EXTENSION_CONFIG = {}
        MPT_PRODUCTS_IDS = "PRD-1111-1111"
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
                "rich": {
                    "class": "logging.StreamHandler",
                    "formatter": "verbose",
                },
            },
            "root": {"handlers": [handler], "level": "INFO"},
            "loggers": {"swo.mpt": {"handlers": [handler], "level": "INFO", "propagate": False}},
        }
        if use_app_insights:
            LOGGING["handlers"]["opentelemetry"] = {
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            }
        APPLICATIONINSIGHTS_CONNECTION_STRING = (
            "InstrumentationKey=12345678-1234-1234-1234-123456789012"
        )

    return MockSettings()


def test_initializer_sets_env(monkeypatch):
    """
    Test that the initializer sets the MPT_INITIALIZER environment variable correctly.
    """
    monkeypatch.delenv("MPT_INITIALIZER", raising=False)
    import importlib

    import swo_aws_extension.initializer as initializer

    importlib.reload(initializer)
    assert os.environ["MPT_INITIALIZER"] == "swo_aws_extension.initializer.initialize"


def test_initialize_basic(monkeypatch, mocker):
    """
    Test the basic initialization of the runtime with default settings.
    """
    mock_settings = make_mock_settings("myext.app", handler="rich")

    monkeypatch.setitem(sys.modules, "django.conf", types.SimpleNamespace(settings=mock_settings))

    django_mock = types.SimpleNamespace(setup=mocker.Mock(), VERSION=(4, 2, 23))

    monkeypatch.setitem(sys.modules, "django", django_mock)

    monkeypatch.setattr(
        "mpt_extension_sdk.runtime.initializer.get_extension_app_config_name",
        lambda group, name: "test.swoext",
    )

    monkeypatch.setattr(
        "mpt_extension_sdk.runtime.initializer.get_extension_variables",
        lambda x: {"config_setting": "value"},
    )

    monkeypatch.setattr("rich.reconfigure", lambda **kwargs: None)

    import swo_aws_extension.initializer as initializer

    options = {"color": True, "debug": True}

    initializer.initialize(options)

    assert mock_settings.DEBUG is True
    assert "test.swoext" in mock_settings.INSTALLED_APPS
    assert mock_settings.EXTENSION_CONFIG["config_setting"] == "value"
    assert mock_settings.LOGGING["root"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["level"] == "DEBUG"
    assert mock_settings.LOGGING["loggers"]["test"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["test"]["level"] == "DEBUG"
    assert mock_settings.MPT_PRODUCTS_IDS == ["PRD-1111-1111"]


def test_initialize_with_app_insights(monkeypatch, mocker, mock_app_insights_instrumentation_key):
    """
    Test the initialization with Application Insights enabled.
    """
    mocker.patch(
        "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter",
        autospec=True,
    )

    mock_settings = make_mock_settings("myext.app", use_app_insights=True, handler="console")

    monkeypatch.setitem(
        sys.modules,
        "django.conf",
        types.SimpleNamespace(settings=mock_settings),
    )

    django_mock = mocker.MagicMock(autospec=True)
    django_mock.setup = mocker.Mock(autospec=True)
    django_mock.VERSION = (4, 2, 23)

    monkeypatch.setitem(sys.modules, "django", django_mock)

    mocker.patch(
        "mpt_extension_sdk.runtime.djapp.conf.extract_product_ids",
        return_value="PRD-1111-1111",
    )

    mocker.patch(
        "mpt_extension_sdk.runtime.utils.get_extension_app_config_name",
        return_value="test.swoext",
    )

    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        f"InstrumentationKey={mock_app_insights_instrumentation_key};"
        f"IngestionEndpoint=https://test.applicationinsights.azure.com/",
    )

    mocker.patch(
        "mpt_extension_sdk.runtime.utils.get_extension_variables",
        return_value={},
    )

    monkeypatch.setenv(
        "APPINSIGHTS_INSTRUMENTATIONKEY",
        mock_app_insights_instrumentation_key,
    )
    mocker.patch("rich.reconfigure", return_value=None)

    mock_instrument_logging = mocker.patch(
        "mpt_extension_sdk.runtime.initializer.instrument_logging"
    )

    mock_botocore = mocker.patch("swo_aws_extension.initializer.BotocoreInstrumentor")

    import swo_aws_extension.initializer as initializer

    options = {"color": False, "debug": False}

    initializer.initialize(options)

    assert mock_settings.LOGGING["root"]["handlers"] == ["console", "opentelemetry"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["handlers"] == ["console", "opentelemetry"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["level"] == "INFO"

    mock_instrument_logging.assert_called_once()
    mock_botocore.return_value.instrument.assert_called_once()
