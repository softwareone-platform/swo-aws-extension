import importlib
import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def clear_initializer_env(monkeypatch):
    monkeypatch.delenv("MPT_INITIALIZER", raising=False)


def make_mock_settings(app_config_name, logging_handler="console", *, use_app_insights=False):
    class MockSettings:
        def __init__(self):
            self.USE_APPLICATIONINSIGHTS = use_app_insights
            self.DEBUG = False
            self.INSTALLED_APPS = []
            self.EXTENSION_CONFIG = {}
            self.MPT_PRODUCTS_IDS = "PRD-1111-1111"
            self.LOGGING = {
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
                "root": {"handlers": [logging_handler], "level": "INFO"},
                "loggers": {
                    "swo.mpt": {"handlers": [logging_handler], "level": "INFO", "propagate": False},
                },
            }
            if use_app_insights:
                self.LOGGING["handlers"]["opentelemetry"] = {
                    "class": "logging.StreamHandler",
                    "formatter": "verbose",
                }
            self.APPLICATIONINSIGHTS_CONNECTION_STRING = (
                "InstrumentationKey=12345678-1234-1234-1234-123456789012"
            )

    return MockSettings()


def test_initializer_sets_env(monkeypatch):
    monkeypatch.delenv("MPT_INITIALIZER", raising=False)
    from swo_aws_extension import initializer  # noqa: PLC0415

    importlib.reload(initializer)  # act

    assert os.environ["MPT_INITIALIZER"] == "swo_aws_extension.initializer.initialize"


@pytest.mark.xfail  # FIXME
def test_initialize_basic(monkeypatch, mocker):
    mock_settings = make_mock_settings("myext.app", logging_handler="rich", use_app_insights=False)
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
    options = {"color": True, "debug": True}
    from swo_aws_extension import initializer  # noqa: PLC0415

    initializer.initialize(options)  # act

    assert mock_settings.DEBUG is True
    assert "test.swoext" in mock_settings.INSTALLED_APPS
    assert mock_settings.EXTENSION_CONFIG["config_setting"] == "value"
    assert mock_settings.LOGGING["root"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["level"] == "DEBUG"
    assert mock_settings.LOGGING["loggers"]["test"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["test"]["level"] == "DEBUG"
    assert mock_settings.MPT_PRODUCTS_IDS == ["PRD-1111-1111"]
    assert mock_settings.AWS_PRODUCT_ID == "PRD-1111-1111"


def test_initialize_with_app_insights(monkeypatch, mocker, mock_app_insights_instrumentation_key):
    mocker.patch(
        "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter",
        autospec=True,
    )
    mock_settings = make_mock_settings(
        "myext.app", logging_handler="console", use_app_insights=True
    )
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
    options = {"color": False, "debug": False}
    from swo_aws_extension import initializer  # noqa: PLC0415

    initializer.initialize(options)  # act

    assert mock_settings.LOGGING["root"]["handlers"] == ["console", "opentelemetry"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["handlers"] == ["console", "opentelemetry"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["level"] == "INFO"
    mock_instrument_logging.assert_called_once()
    mock_botocore.return_value.instrument.assert_called_once()
