import pytest

from swo_aws_extension.swo.crm_service.config import CRMConfig, CRMConfigError


@pytest.fixture
def crm_settings(settings):
    settings.EXTENSION_CONFIG = {
        "CRM_API_BASE_URL": "https://crm.test.com/",
        "CRM_OAUTH_URL": "https://oauth.test.com/token",
        "CRM_CLIENT_ID": "test-client-id",
        "CRM_CLIENT_SECRET": "test-client-secret",
        "CRM_AUDIENCE": "test-audience",
    }
    return settings


def test_from_settings_with_all_values(crm_settings):
    result = CRMConfig.from_settings()

    assert result.base_url == "https://crm.test.com/"
    assert result.oauth_url == "https://oauth.test.com/token"
    assert result.client_id == "test-client-id"
    assert result.client_secret == "test-client-secret"
    assert result.audience == "test-audience"


def test_from_settings_error_when_keys_missing(settings):
    settings.EXTENSION_CONFIG = {}

    with pytest.raises(CRMConfigError, match="Missing required CRM configuration keys"):
        CRMConfig.from_settings()
