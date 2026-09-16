import logging
from functools import wraps
from urllib.parse import urljoin
from uuid import uuid4

import requests
from django.conf import settings
from requests import HTTPError

from swo_aws_extension.swo.finops.errors import (
    FinOpsHttpError,
    FinOpsNotFoundError,
)

logger = logging.getLogger(__name__)

TIMEOUT = 60


def wrap_http_error(func):
    """Decorator to wrap HTTP errors into FinOps errors."""

    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPError as err:
            if err.response.status_code == 404:
                raise FinOpsNotFoundError(err.response.text) from err
            raise FinOpsHttpError(err.response.status_code, err.response.text) from err

    return _wrapper


class FinOpsClient(requests.Session):
    """Client to interact with the FinOps extension operations API.

    Requests are authenticated with the Marketplace API token shared by the extension.
    """

    def __init__(self, base_url: str, api_token: str):
        super().__init__()
        base_url = base_url if base_url[-1] == "/" else f"{base_url}/"
        self.base_url = base_url
        self.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def request(self, method: str, url: str, *args, **kwargs):
        """Makes HTTP request against the FinOps extension operations API."""
        url = url[1:] if url[0] == "/" else url
        url = urljoin(self.base_url, url)
        headers = {"X-Request-Id": str(uuid4()), **kwargs.pop("headers", {})}
        kwargs.setdefault("timeout", TIMEOUT)
        return super().request(method, url, *args, headers=headers, **kwargs)

    @wrap_http_error
    def create_entitlement(
        self, affiliate_external_id: str, datasource_id: str, name: str = "AWS"
    ) -> dict:
        """Create new FinOps entitlement."""
        response = self.post(
            url="entitlements",
            json={
                "name": name,
                "affiliate_external_id": affiliate_external_id,
                "datasource_id": datasource_id,
            },
        )
        response.raise_for_status()
        return response.json()

    @wrap_http_error
    def get_entitlement(self, entitlement_id: str) -> dict:
        """Get the FinOps entitlement details by ID."""
        response = self.get(url=f"entitlements/{entitlement_id}")
        response.raise_for_status()
        return response.json()

    @wrap_http_error
    def delete_entitlement(self, entitlement_id: str) -> None:
        """Delete the FinOps entitlement by ID."""
        response = self.delete(url=f"entitlements/{entitlement_id}")
        response.raise_for_status()

    @wrap_http_error
    def terminate_entitlement(self, entitlement_id: str) -> dict:
        """Terminate the FinOps entitlement by ID."""
        response = self.post(url=f"entitlements/{entitlement_id}/terminate")
        response.raise_for_status()
        return response.json()

    @wrap_http_error
    def get_entitlement_by_datasource(self, datasource_id: str) -> dict | None:
        """Get the FinOps entitlement details by datasource ID."""
        response = self.get(url=f"entitlements?datasource_id={datasource_id}&limit=1")
        response.raise_for_status()
        result = response.json()
        result_items = result.get("items", [])
        total = result.get("total", 0)
        return result_items[0] if total > 0 and result_items else None


class _FinOpsClientFactory:
    """Factory for FinOps client singleton."""

    _instance: FinOpsClient | None = None

    @classmethod
    def get_client(cls) -> FinOpsClient:
        """Get FinOps client singleton instance."""
        if cls._instance is not None:
            return cls._instance

        cls._instance = FinOpsClient(
            settings.EXTENSION_CONFIG["FFC_OPERATIONS_API_BASE_URL"],
            settings.MPT_API_TOKEN,
        )
        return cls._instance


def get_ffc_client() -> FinOpsClient:
    """Get FinOps client singleton instance."""
    return _FinOpsClientFactory.get_client()
