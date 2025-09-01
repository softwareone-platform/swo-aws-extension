import os

import pytest

from swo_aws_extension.aws.config import Config


class DummyConfig(Config):
    """Expose get_file_contents for direct call without __init__ side-effects."""
    def __init__(self):
        pass


def test_get_file_contents_exists(tmp_path):
    p = tmp_path / "secret.txt"
    content = "super-secret"
    p.write_text(content, encoding="utf-8")

    cfg = DummyConfig()
    assert cfg.get_file_contents(str(p)) == content


def test_get_file_contents_not_exists(tmp_path):
    p = tmp_path / "nope.txt"
    cfg = DummyConfig()
    with pytest.raises(FileNotFoundError):
        cfg.get_file_contents(str(p))


def test_setup_azure_env_does_nothing_if_password_set(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_CLIENT_CERTIFICATE_PASSWORD", "already")
    monkeypatch.setenv("AZURE_CLIENT_PASSWORD_PATH", str(tmp_path / "whatever"))

    cfg = DummyConfig()
    cfg.setup_azure_env()
    # should not overwrite
    assert os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] == "already"


def test_setup_azure_env_reads_file_if_path_set(monkeypatch, tmp_path):
    secret_file = tmp_path / "pwd.txt"
    secret_file.write_text("from-file", encoding="utf-8")

    monkeypatch.delenv("AZURE_CLIENT_CERTIFICATE_PASSWORD", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_PASSWORD_PATH", str(secret_file))

    cfg = DummyConfig()
    cfg.setup_azure_env()
    assert os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] == "from-file"


def test_init_triggers_setup(tmp_path, monkeypatch):
    # ensure __init__ picks up file path
    secret_file = tmp_path / "init.txt"
    secret_file.write_text("auto-set", encoding="utf-8")

    monkeypatch.delenv("AZURE_CLIENT_CERTIFICATE_PASSWORD", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_PASSWORD_PATH", str(secret_file))

    # instantiating should call setup_azure_env
    Config()
    assert os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] == "auto-set"
