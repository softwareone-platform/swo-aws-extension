import os

from django.conf import settings


class Config:
    @staticmethod
    def _patch_path(file_path):
        """
        Fixes relative paths to be from the project root.
        """
        if not os.path.isabs(file_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            file_path = os.path.abspath(os.path.join(project_root, file_path))
        return file_path

    def get_file_contents(self, file_path: str) -> str:
        """
        Get the contents of a file.
        """
        file_path = self._patch_path(file_path)
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
    def ccp_oauth_credentials_scope(self) -> str:
        """
        Get the scope for the CCP OAuth.
        """
        return settings.EXTENSION_CONFIG["CCP_OAUTH_CREDENTIALS_SCOPE"]

    @property
    def minimum_mpa_threshold(self) -> int:
        """
        Get the minimum MPA threshold.
        """
        return settings.EXTENSION_CONFIG["MINIMUM_MPA_THRESHOLD"]

    @property
    def billing_discount_base(self) -> int:
        """
        Get the base billing discount.
        """
        return int(settings.EXTENSION_CONFIG.get("BILLING_DISCOUNT_BASE", 7))

    @property
    def billing_discount_incentivate(self) -> int:
        """
        Get the billing discount for incentivate services.
        """
        return int(settings.EXTENSION_CONFIG.get("BILLING_DISCOUNT_INCENTIVATE", 12))

    @property
    def billing_discount_support_enterprise(self) -> int:
        """
        Get the billing discount for enterprise support.
        """
        return settings.EXTENSION_CONFIG.get("BILLING_DISCOUNT_SUPPORT_ENTERPRISE", 35)

    @property
    def billing_discount_tolerance_rate(self) -> int:
        """
        Get the billing discount for enterprise support.
        """
        return int(settings.EXTENSION_CONFIG.get("BILLING_DISCOUNT_TOLERANCE_RATE", 1))

    @property
    def mpt_portal_base_url(self) -> str:
        """
        Get the base URL for the MPT portal.
        """
        return settings.MPT_PORTAL_BASE_URL


_CONFIG = None


def get_config():
    global _CONFIG
    if not _CONFIG:
        _CONFIG = Config()
    return _CONFIG
