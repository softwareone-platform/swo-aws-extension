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
    def management_role_name(self) -> str:
        """Get the Management role name."""
        return settings.EXTENSION_CONFIG.get("MANAGEMENT_ROLE")

    @property
    def querying_timeout_days(self) -> int:
        """Get the timeout for channel handshake in days."""
        return int(settings.EXTENSION_CONFIG["QUERYING_TIMEOUT_DAYS"])

    @property
    def customer_roles_querying_timeout_days(self) -> int:
        """Get the timeout for customer roles querying in days."""
        return int(settings.EXTENSION_CONFIG["CUSTOMER_ROLES_QUERYING_TIMEOUT_DAYS"])

    @property
    def cloud_orchestrator_api_base_url(self) -> str:
        """Get the base URL for the Cloud Orchestrator API."""
        return settings.EXTENSION_CONFIG["CLOUD_ORCHESTRATOR_API_BASE_URL"]

    @property
    def crm_api_base_url(self) -> str:
        """Get the base URL for the CRM API."""
        return settings.EXTENSION_CONFIG["CRM_API_BASE_URL"]

    @property
    def crm_oauth_url(self) -> str:
        """Get the OAuth URL for the CRM API."""
        return settings.EXTENSION_CONFIG["CRM_OAUTH_URL"]

    @property
    def crm_client_id(self) -> str:
        """Get the client ID for the CRM API."""
        return settings.EXTENSION_CONFIG["CRM_CLIENT_ID"]

    @property
    def crm_client_secret(self) -> str:
        """Get the client secret for the CRM API."""
        return settings.EXTENSION_CONFIG["CRM_CLIENT_SECRET"]

    @property
    def crm_audience(self) -> str:
        """Get the audience for the CRM API."""
        return settings.EXTENSION_CONFIG["CRM_AUDIENCE"]

    @property
    def aws_ses_access_key(self) -> str:
        """Get the AWS SES access key."""
        return settings.EXTENSION_CONFIG["AWS_SES_CREDENTIALS"].split(":")[0]

    @property
    def aws_ses_secret_key(self) -> str:
        """Get the AWS SES secret key."""
        return settings.EXTENSION_CONFIG["AWS_SES_CREDENTIALS"].split(":")[1]

    @property
    def aws_ses_region(self) -> str:
        """Get the AWS SES region."""
        return settings.EXTENSION_CONFIG["AWS_SES_REGION"]

    @property
    def email_notifications_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return bool(int(settings.EXTENSION_CONFIG.get("EMAIL_NOTIFICATIONS_ENABLED", 0)))

    @property
    def email_notifications_sender(self) -> str:
        """Get the email notifications sender."""
        return settings.EXTENSION_CONFIG["EMAIL_NOTIFICATIONS_SENDER"]

    @property
    def deploy_services_feature_recipients(self) -> list[str]:
        """Get the deploy services feature recipients."""
        recipients = settings.EXTENSION_CONFIG.get("DEPLOY_SERVICES_FEATURE_RECIPIENTS", "")
        return [email.strip() for email in recipients.split(",") if email.strip()]

    def _patch_path(self, file_path):
        """Fixes relative paths to be from the project root."""
        path = Path(file_path)
        if not path.is_absolute():  # pragma: no cover
            project_root = Path(__file__).resolve().parent.parent
            path = (project_root / path).resolve()
        return path


_CONFIG = None


def get_config() -> Config:
    """Get configuration."""
    global _CONFIG  # noqa: PLW0603 WPS420
    if not _CONFIG:
        _CONFIG = Config()
    return _CONFIG
