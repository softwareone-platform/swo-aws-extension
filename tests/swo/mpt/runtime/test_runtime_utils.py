from ninja import NinjaAPI
from mpt_extension_sdk.core.events.registry import EventsRegistry
from mpt_extension_sdk.runtime.utils import (
    get_events_registry,
    get_extension,
    get_extension_app_config_name,
    get_extension_app_config,
)


def test_get_extension_app_config_name():
    group = "swo.mpt.ext"
    name = "app_config"
    app_config_name = get_extension_app_config_name(group=group, name=name)
    assert app_config_name == "swo_aws_extension.apps.ExtensionConfig"


def test_get_extension_appconfig():
    group = "swo.mpt.ext"
    name = "app_config"
    appconfig = get_extension_app_config(group=group, name=name)
    assert appconfig.name == "swo_aws_extension"
    assert appconfig.label == "swo_aws_extension"


def test_get_extension():
    group = "swo.mpt.ext"
    name = "app_config"
    extension = get_extension(group=group, name=name)
    assert extension is not None
    assert isinstance(extension.api, NinjaAPI)
    assert isinstance(extension.events, EventsRegistry)


def test_get_events_registry():
    group = "swo.mpt.ext"
    name = "app_config"
    events_registry = get_events_registry(group=group, name=name)
    assert events_registry.listeners is not None
    assert isinstance(events_registry.listeners, dict)
