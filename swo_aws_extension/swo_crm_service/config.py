from django.conf import settings


class CRMConfig:
    """CRM access."""

    @property
    def base_url(self) -> str:
        """Base CRM url."""
        return settings.EXTENSION_CONFIG["CRM_API_BASE_URL"]

    @property
    def oauth_url(self) -> str:
        """CRM OAuth url."""
        return settings.EXTENSION_CONFIG["CRM_OAUTH_URL"]

    @property
    def client_id(self) -> str:
        """CRM client id."""
        return settings.EXTENSION_CONFIG["CRM_CLIENT_ID"]

    @property
    def client_secret(self) -> str:
        """CRM client secret."""
        return settings.EXTENSION_CONFIG["CRM_CLIENT_SECRET"]

    @property
    def audience(self) -> str:
        """CRM audience."""
        return settings.EXTENSION_CONFIG["CRM_AUDIENCE"]
