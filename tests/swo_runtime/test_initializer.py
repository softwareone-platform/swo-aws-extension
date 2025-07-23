import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def clear_initializer_env(monkeypatch):
    monkeypatch.delenv("MPT_INITIALIZER", raising=False)


def make_mock_settings(app_config_name, use_app_insights=False):
    class MockSettings:
        USE_APPLICATIONINSIGHTS = use_app_insights
        DEBUG = False
        INSTALLED_APPS = []
        EXTENSION_CONFIG = {}
        MPT_PRODUCTS_IDS = "PRD-1111-1111"
        LOGGING = {
            "root": {"handlers": []},
            "loggers": {"swo.mpt": {"handlers": [], "level": "INFO"}},
        }
        APPLICATIONINSIGHTS_CONNECTION_STRING = "InstrumentationKey=00000000-0000-0000-0000-000000000000"
    return MockSettings()

def test_initializer_sets_env(monkeypatch):
    monkeypatch.delenv("MPT_INITIALIZER", raising=False)
    import importlib

    import swo_runtime.initializer as initializer
    importlib.reload(initializer)
    assert os.environ["MPT_INITIALIZER"] == "swo_runtime.initializer.initialize"

def test_initialize_basic(monkeypatch, mocker):
    mock_settings = make_mock_settings("myext.app")

    monkeypatch.setitem(sys.modules, "django.conf", types.SimpleNamespace(settings=mock_settings))

    django_mock = types.SimpleNamespace(setup=mocker.Mock(), VERSION=(4, 2, 23))

    monkeypatch.setitem(sys.modules, "django", django_mock)



    monkeypatch.setattr(
        "swo_runtime.initializer.get_extension_app_config_name",
        lambda group, name: "test.swoext",
    )

    monkeypatch.setattr(
        "swo_runtime.initializer.get_extension_variables",
        lambda x: {"config_setting": "value"},
    )

    monkeypatch.setattr("rich.reconfigure", lambda **kwargs: None)

    import swo_runtime.initializer as initializer

    options = {"color": True, "debug": True}

    initializer.initialize(options)

    assert mock_settings.DEBUG is True
    assert "test.swoext" in mock_settings.INSTALLED_APPS
    assert mock_settings.EXTENSION_CONFIG["config_setting"] == "value"
    assert mock_settings.LOGGING["root"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["handlers"] == ["rich"]
    assert mock_settings.LOGGING["loggers"]["swo.mpt"]["level"] == "DEBUG"
    assert mock_settings.MPT_PRODUCTS_IDS == ["PRD-1111-1111"]


def test_initialize_with_app_insights(monkeypatch, mocker):
    mocker.patch(
        "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter",
        autospec=True,
    )

    mock_settings = make_mock_settings("myext.app", use_app_insights=True)

    monkeypatch.setitem(
        sys.modules,
        "django.conf",
        types.SimpleNamespace(settings=mock_settings),
    )

    django_mock = types.SimpleNamespace(setup=mocker.Mock(), VERSION=(4, 2, 23))

    monkeypatch.setitem(sys.modules, "django", django_mock)

    monkeypatch.setattr(
        "mpt_extension_sdk.runtime.djapp.conf.extract_product_ids",
        lambda x: "PRD-1111-1111",
    )

    monkeypatch.setattr(
        "swo_runtime.initializer.get_extension_app_config_name",
        lambda group, name: "test.swoext",
    )

    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )

    monkeypatch.setattr(
        "swo_runtime.initializer.get_extension_variables",
        lambda x: {},
    )

    monkeypatch.setenv(
        "APPINSIGHTS_INSTRUMENTATIONKEY",
        "00000000-0000-0000-0000-000000000000",
    )
    monkeypatch.setattr("rich.reconfigure", lambda **kwargs: None)


    mock_instrument_logging = mocker.patch("swo_runtime.initializer.instrument_logging")


    mock_botocore = mocker.patch("swo_runtime.initializer.BotocoreInstrumentor")

    import swo_runtime.initializer as initializer

    options = {"color": False, "debug": False}

    initializer.initialize(options)

    mock_instrument_logging.assert_called_once()
    mock_botocore.return_value.instrument.assert_called_once()
