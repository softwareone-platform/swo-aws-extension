import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from mpt_extension_sdk.core.extension import Extension

from swo_aws_extension.apps import ExtensionConfig


def test_app_config():
    result = ExtensionConfig.extension

    assert isinstance(result, Extension)


def test_products_empty(settings):
    settings.MPT_PRODUCTS_IDS = ""
    app = apps.get_app_config("swo_aws_extension")

    with pytest.raises(ImproperlyConfigured) as error:
        app.ready()

    assert "MPT_PRODUCTS_IDS is missing or empty" in str(error.value)


def test_products_not_defined(settings):
    settings.MPT_PRODUCTS_IDS = None
    app = apps.get_app_config("swo_aws_extension")

    with pytest.raises(ImproperlyConfigured) as error:
        app.ready()

    assert "MPT_PRODUCTS_IDS is missing or empty" in str(error.value)


def test_webhook_secret_not_defined(settings):
    settings.EXTENSION_CONFIG = {}
    app = apps.get_app_config("swo_aws_extension")

    with pytest.raises(ImproperlyConfigured) as error:
        app.ready()

    assert "Please, specify it in EXT_WEBHOOKS_SECRETS environment variable." in str(error.value)
