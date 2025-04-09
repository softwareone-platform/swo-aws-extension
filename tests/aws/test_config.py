from swo_aws_extension.aws.config import get_config


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
