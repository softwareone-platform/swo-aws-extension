from django.core.wsgi import get_wsgi_application
from mpt_extension_sdk.runtime.workers import (
    ExtensionWebApplication,
    start_event_consumer,
    start_gunicorn,
)


def test_extension_web_application(mock_gunicorn_logging_config):
    """
    Test the ExtensionWebApplication initialization with gunicorn options.
    """
    gunicorn_options = {
        "bind": "localhost:8080",
        "logconfig_dict": mock_gunicorn_logging_config,
    }
    wsgi_app = get_wsgi_application()
    ext_web_app = ExtensionWebApplication(wsgi_app, gunicorn_options)
    assert ext_web_app.application == wsgi_app
    assert ext_web_app.options == gunicorn_options


def test_extension_web_application_load_config(mock_gunicorn_logging_config):
    """
    Test the loading of gunicorn options into the ExtensionWebApplication.
    """
    gunicorn_options = {
        "bind": "localhost:8080",
        "logconfig_dict": mock_gunicorn_logging_config,
    }
    wsgi_app = get_wsgi_application()
    ext_web_app = ExtensionWebApplication(wsgi_app, gunicorn_options)
    ext_web_app.load_config()
    assert ext_web_app.application == wsgi_app
    assert ext_web_app.options == gunicorn_options


def test_event_consumer(
    mock_gunicorn_logging_config,
    mocker,
    mock_worker_call_command_path,
    mock_initialize_extension_path,
):
    """
    Test the event consumer initialization with gunicorn options.
    """
    from django.conf import settings
    if "swo.mpt" not in settings.LOGGING["loggers"]:
        settings.LOGGING["loggers"]["swo.mpt"] = {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        }
    gunicorn_options = {
        "bind": "localhost:8080",
        "logconfig_dict": mock_gunicorn_logging_config,
    }
    mock_initialize = mocker.patch(mock_initialize_extension_path)
    mock_call_command = mocker.patch(mock_worker_call_command_path)
    start_event_consumer(gunicorn_options)
    mock_initialize.assert_called_once()
    mock_call_command.assert_called_once()


def test_gunicorn(
    mocker,
    mock_gunicorn_logging_config,
    mock_initialize_extension_path,
    mock_get_wsgi_application_path,
):
    """
    Test the gunicorn server startup with the provided logging configuration.
    """
    from django.conf import settings
    if "swo.mpt" not in settings.LOGGING["loggers"]:
        settings.LOGGING["loggers"]["swo.mpt"] = {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        }
    mock_initialize = mocker.patch(mock_initialize_extension_path)
    mock_run = mocker.patch.object(ExtensionWebApplication, "run", return_value=None)
    mock_wsgi = mocker.patch(mock_get_wsgi_application_path)
    gunicorn_options = {
        "bind": "localhost:8080",
        "logconfig_dict": mock_gunicorn_logging_config,
    }
    start_gunicorn(gunicorn_options)
    mock_initialize.assert_called_once()
    mock_run.assert_called_once()
    mock_wsgi.assert_called_once()
