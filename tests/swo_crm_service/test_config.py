from swo_aws_extension.swo_crm_service.config import CRMConfig


def test_crm_config(mock_settings):
    config = CRMConfig()
    assert config.base_url == "https://api.example.com"
    assert config.oauth_url == "https://auth.example.com"
    assert config.client_id == "client_id"
    assert config.client_secret == "client_secret"
    assert config.audience == "audience"
