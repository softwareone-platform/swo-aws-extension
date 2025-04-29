import os

from django.conf import settings


class Config:
    def get_file_contents(self, file_path: str) -> str:
        """
        Get the contents of a file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        with open(file_path, encoding="utf-8") as file:
            return file.read()

    def setup_azure_env(self):
        password = os.environ.get("AZURE_CLIENT_CERTIFICATE_PASSWORD", None)
        password_path = os.environ.get("AZURE_CLIENT_PASSWORD_PATH", None)
        if not password and password_path:
            os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] = self.get_file_contents(password_path)

    def __init__(self):
        self.setup_azure_env()

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
