from django.conf import settings


class Config:
    @property
    def ccp_client_id(self) -> str:
        return settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]

    @property
    def aws_openid_scope(self) -> str:
        return settings.EXTENSION_CONFIG["AWS_OPENID_SCOPE"]

    @property
    def ccp_oauth_url(self) -> str:
        return settings.EXTENSION_CONFIG["CCP_OAUTH_URL"]

    @property
    def aws_region(self) -> str:
        return settings.EXTENSION_CONFIG["AWS_REGION"]

    @property
    def ccp_scope(self):
        return settings.EXTENSION_CONFIG["CCP_SCOPE"]

    @property
    def ccp_key_vault_secret_name(self):
        return settings.EXTENSION_CONFIG["CCP_KEY_VAULT_SECRET_NAME"]

    @property
    def ccp_api_base_url(self) -> str:
        """
        Get the base URL for the CCP API.
        """
        return settings.EXTENSION_CONFIG["CCP_API_BASE_URL"]

    @property
    def ccp_oauth_scope(self) -> str:
        """
        Get the scope for the CCP OAuth.
        """
        return settings.EXTENSION_CONFIG["CCP_OAUTH_SCOPE"]

    @property
    def minimum_mpa_threshold(self) -> int:
        """
        Get the minimum MPA threshold.
        """
        return settings.EXTENSION_CONFIG["MINIMUM_MPA_THRESHOLD"]


_CONFIG = None


def get_config():
    global _CONFIG
    if not _CONFIG:
        _CONFIG = Config()
    return _CONFIG
