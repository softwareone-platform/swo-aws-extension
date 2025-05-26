from django.conf import settings


class CRMConfig:
    @property
    def base_url(self) -> str:
        return settings.EXTENSION_CONFIG["CRM_API_BASE_URL"]

    @property
    def oauth_url(self) -> str:
        return settings.EXTENSION_CONFIG["CRM_OAUTH_URL"]

    @property
    def client_id(self) -> str:
        return settings.EXTENSION_CONFIG["CRM_CLIENT_ID"]

    @property
    def client_secret(self) -> str:
        return settings.EXTENSION_CONFIG["CRM_CLIENT_SECRET"]

    @property
    def audience(self) -> str:
        return settings.EXTENSION_CONFIG["CRM_AUDIENCE"]
