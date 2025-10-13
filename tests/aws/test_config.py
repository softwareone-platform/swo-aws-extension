import os

import pytest

from swo_aws_extension.aws.config import Config, get_config


def test_ccp_client_id(settings):
    settings.EXTENSION_CONFIG["CCP_CLIENT_ID"] = "test_client_id"

    config = get_config()

    assert config.ccp_client_id == "test_client_id"


def test_openid_scope(settings):
    settings.EXTENSION_CONFIG["AWS_OPENID_SCOPE"] = "test_scope"

    config = get_config()

    assert config.aws_openid_scope == "test_scope"


def test_ccp_oauth_url(settings):
    settings.EXTENSION_CONFIG["CCP_OAUTH_URL"] = "https://example.com/oauth2/token"

    config = get_config()

    assert config.ccp_oauth_url == "https://example.com/oauth2/token"


def test_ccp_scope(settings):
    settings.EXTENSION_CONFIG["CCP_SCOPE"] = "test_ccp_scope"

    config = get_config()

    assert config.ccp_scope == "test_ccp_scope"


def test_ccp_key_vault_secret_name(settings):
    settings.EXTENSION_CONFIG["CCP_KEY_VAULT_SECRET_NAME"] = "test_secret_name"

    config = get_config()

    assert config.ccp_key_vault_secret_name == "test_secret_name"


def test_get_file_contents_exists(tmp_path):
    path = tmp_path / "secret.txt"
    file_content = "super-secret"
    path.write_text(file_content, encoding="utf-8")

    cfg = Config()

    assert cfg.get_file_contents(str(path)) == file_content


def test_get_file_contents_not_exists(tmp_path):
    path = tmp_path / "nope.txt"
    cfg = Config()

    with pytest.raises(FileNotFoundError):
        cfg.get_file_contents(str(path))


def test_azure_env_password_already_set(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_CLIENT_CERTIFICATE_PASSWORD", "already")
    monkeypatch.setenv("AZURE_CLIENT_PASSWORD_PATH", str(tmp_path / "whatever"))
    cfg = Config()

    cfg.setup_azure_env()

    assert os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] == "already"


def test_azure_env_reads_file_if_path_set(monkeypatch, tmp_path):
    secret_file = tmp_path / "pwd.txt"
    secret_file.write_text("from-file", encoding="utf-8")
    monkeypatch.delenv("AZURE_CLIENT_CERTIFICATE_PASSWORD", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_PASSWORD_PATH", str(secret_file))
    cfg = Config()

    cfg.setup_azure_env()

    assert os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] == "from-file"


def test_init_triggers_setup(tmp_path, monkeypatch):
    # ensure __init__ picks up file path
    secret_file = tmp_path / "init.txt"
    secret_file.write_text("auto-set", encoding="utf-8")
    monkeypatch.delenv("AZURE_CLIENT_CERTIFICATE_PASSWORD", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_PASSWORD_PATH", str(secret_file))

    Config()

    assert os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] == "auto-set"
