from swo_aws_extension.aws.config import get_config


def test_ccp_client_id(settings):
    settings.EXTENSION_CONFIG["CCP_CLIENT_ID"] = "test_client_id"
    config = get_config()
    assert config.ccp_client_id == "test_client_id"


def test_ccp_client_secret(settings):
    settings.EXTENSION_CONFIG["CCP_CLIENT_SECRET"] = "test_client_secret"
    config = get_config()
    assert config.ccp_client_secret == "test_client_secret"


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


def test_mpt_key_vault_name(settings):
    settings.MPT_KEY_VAULT_NAME = "test_key_vault_name"
    config = get_config()
    assert config.mpt_key_vault_name == "test_key_vault_name"


def test_ccp_mpt_api_url(settings):
    settings.EXTENSION_CONFIG["CCP_MPT_API_URL"] = "https://example.com/mpt/api"
    config = get_config()
    assert config.ccp_mpt_api_url == "https://example.com/mpt/api"


def test_azure_client_id(settings):
    settings.EXTENSION_CONFIG["AZURE_CLIENT_ID"] = "test_azure_client_id"
    config = get_config()
    assert config.azure_client_id == "test_azure_client_id"


def test_azure_tenant_id(settings):
    settings.EXTENSION_CONFIG["AZURE_TENANT_ID"] = "test_azure_tenant_id"
    config = get_config()
    assert config.azure_tenant_id == "test_azure_tenant_id"


def test_azure_client_certificate_password(settings):
    settings.EXTENSION_CONFIG["AZURE_CLIENT_CERTIFICATE_PASSWORD"] = (
        "test_azure_client_certificate_password"
    )
    config = get_config()
    assert config.azure_client_certificate_password == "test_azure_client_certificate_password"


def test_azure_client_certificate_path(settings):
    settings.EXTENSION_CONFIG["AZURE_CLIENT_CERTIFICATE_PATH"] = (
        "test_azure_client_certificate_path"
    )
    config = get_config()
    assert config.azure_client_certificate_path == "test_azure_client_certificate_path"
