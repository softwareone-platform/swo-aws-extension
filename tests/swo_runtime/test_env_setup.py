
import importlib
import os
import sys


def test_sets_django_settings_module_when_unset(monkeypatch):
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    sys.modules.pop("swo_runtime.env_setup", None)
    import swo_runtime.env_setup

    importlib.reload(swo_runtime.env_setup)
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "swo_runtime.default"


def test_does_not_override_existing_django_settings_module(monkeypatch):
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "custom.settings")
    sys.modules.pop("swo_runtime.env_setup", None)
    import swo_runtime.env_setup

    importlib.reload(swo_runtime.env_setup)
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "custom.settings"
