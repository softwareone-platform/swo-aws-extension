from django.conf import settings


class Config:
    @property
    def ccp_client_id(self) -> str:
        return settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]

    @property
    def ccp_client_secret(self) -> str:
        return self._get_client_secret()

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
    def mpt_key_vault_name(self):
        return settings.MPT_KEY_VAULT_NAME

    @property
    def ccp_mpt_api_url(self) -> str:
        return settings.EXTENSION_CONFIG["CCP_MPT_API_URL"]

    @property
    def azure_client_id(self) -> str:
        return settings.EXTENSION_CONFIG["AZURE_CLIENT_ID"]

    @property
    def azure_tenant_id(self) -> str:
        return settings.EXTENSION_CONFIG["AZURE_TENANT_ID"]

    @property
    def azure_client_certificate_password(self) -> str:
        return settings.EXTENSION_CONFIG["AZURE_CLIENT_CERTIFICATE_PASSWORD"]

    @property
    def azure_client_certificate_path(self) -> str:
        return settings.EXTENSION_CONFIG["AZURE_CLIENT_CERTIFICATE_PATH"]

    @staticmethod
    def _get_client_secret():
        """
        Get the client secrets from the settings.
        """
        # TODO Logic to get the Secrent from Azure key vault will be done in separate PR
        return settings.EXTENSION_CONFIG["CCP_CLIENT_SECRET"]


_CONFIG = None


def get_config():
    global _CONFIG
    if not _CONFIG:
        _CONFIG = Config()
    return _CONFIG
