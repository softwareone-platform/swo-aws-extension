import os
from pathlib import Path

from django.conf import settings


class Config:
    """AWS extension configuration."""

    def __init__(self):
        self.setup_azure_env()

    def get_file_contents(self, file_path: str) -> str:
        """Get the contents of a file."""
        path = self._patch_path(file_path)
        if not path.exists():
            raise FileNotFoundError(path)

        return path.read_text(encoding="utf-8")

    def setup_azure_env(self):
        """Setup azure env."""
        password = os.environ.get("AZURE_CLIENT_CERTIFICATE_PASSWORD", None)
        password_path = os.environ.get("AZURE_CLIENT_PASSWORD_PATH", None)
        if not password and password_path:
            os.environ["AZURE_CLIENT_CERTIFICATE_PASSWORD"] = self.get_file_contents(password_path)

    @property
    def ccp_client_id(self) -> str:
        """CCP client id."""
        return settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]

    @property
    def aws_openid_scope(self) -> str:
        """CCP aws openid scope."""
        return settings.EXTENSION_CONFIG["AWS_OPENID_SCOPE"]

    @property
    def ccp_oauth_url(self) -> str:
        """CCP oauth url."""
        return settings.EXTENSION_CONFIG["CCP_OAUTH_URL"]

    @property
    def ccp_scope(self):
        """CCP scope."""
        return settings.EXTENSION_CONFIG["CCP_SCOPE"]

    @property
    def ccp_key_vault_secret_name(self):
        """CCP keyvault secret name."""
        return settings.EXTENSION_CONFIG["CCP_KEY_VAULT_SECRET_NAME"]

    @property
    def ccp_api_base_url(self) -> str:
        """Get the base URL for the CCP API."""
        return settings.EXTENSION_CONFIG["CCP_API_BASE_URL"]

    @property
    def ccp_oauth_scope(self) -> str:
        """Get the scope for the CCP OAuth."""
        return settings.EXTENSION_CONFIG["CCP_OAUTH_SCOPE"]

    @property
    def ccp_oauth_credentials_scope(self) -> str:
        """Get the scope for the CCP OAuth."""
        return settings.EXTENSION_CONFIG["CCP_OAUTH_CREDENTIALS_SCOPE"]

    @property
    def apn_role_name(self) -> str:
        """Get the APN role name."""
        return settings.EXTENSION_CONFIG["APN_ROLE_NAME"]

    @property
    def apn_account_id(self) -> str:
        """Get the APN account ID."""
        return settings.EXTENSION_CONFIG["APN_ACCOUNT_ID"]

    @property
    def onboard_customer_role_name(self) -> str:
        """Get the Onboard Customer role name."""
        return settings.EXTENSION_CONFIG.get("ONBOARD_CUSTOMER_ROLE")

    @property
    def management_role_name(self) -> str:
        """Get the Management role name."""
        return settings.EXTENSION_CONFIG.get("MANAGEMENT_ROLE")

    def _patch_path(self, file_path):
        """Fixes relative paths to be from the project root."""
        path = Path(file_path)
        if not path.is_absolute():  # pragma: no cover
            project_root = Path(__file__).resolve().parent.parent
            path = (project_root / path).resolve()
        return path


_CONFIG = None


def get_config():
    """Get configuration."""
    global _CONFIG  # noqa: PLW0603 WPS420
    if not _CONFIG:
        _CONFIG = Config()
    return _CONFIG
