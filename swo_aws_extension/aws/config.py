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
