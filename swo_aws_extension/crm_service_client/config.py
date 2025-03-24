from django.conf import settings

from swo_aws_extension.openid import get_openid_token
from swo_crm_service_client import CRMServiceClient

SERVICE_CLIENT = None


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


def get_crm_access_token():
    config = CRMConfig()
    response = get_openid_token(
        endpoint=config.oauth_url,
        client_id=config.client_id,
        client_secret=config.client_secret,
        scope=None,
        audience=config.audience,
    )
    return response["access_token"]


def get_service_client() -> CRMServiceClient:
    config = CRMConfig()
    global SERVICE_CLIENT
    if not SERVICE_CLIENT:
        SERVICE_CLIENT = CRMServiceClient(
            base_url=config.base_url,
            api_token=get_crm_access_token(),
        )
    return SERVICE_CLIENT
