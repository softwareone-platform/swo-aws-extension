import datetime as dt
import logging
from functools import wraps
from urllib.parse import urljoin
from uuid import uuid4

import jwt
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
    """Client to interact with FinOps API."""

    def __init__(self, base_url: str, sub: str, secret: str):
        super().__init__()
        self._sub = sub
        self._secret = secret
        self._jwt: str | None = None
        base_url = base_url if base_url[-1] == "/" else f"{base_url}/"
        self.base_url = base_url

    def request(self, method: str, url: str, *args, **kwargs):
        """Makes HTTP request with authentication."""
        self._refresh_token_if_needed()
        self.headers.update(self._get_headers())
        url = url[1:] if url[0] == "/" else url
        url = urljoin(self.base_url, url)
        kwargs.setdefault("timeout", TIMEOUT)
        return super().request(method, url, *args, **kwargs)

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

    def _get_headers(self) -> dict:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self._jwt}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Request-Id": str(uuid4()),
        }

    def _refresh_token_if_needed(self) -> None:
        """Refresh JWT token if expired or not set."""
        if not self._jwt or self._is_token_expired():
            now = dt.datetime.now(tz=dt.UTC)
            self._jwt = jwt.encode(
                {
                    "sub": self._sub,
                    "exp": now + dt.timedelta(minutes=5),
                    "nbf": now,
                    "iat": now,
                },
                self._secret,
                algorithm="HS256",
            )

    def _is_token_expired(self) -> bool:
        """Check if the JWT token is expired."""
        try:
            jwt.decode(self._jwt, self._secret, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return True
        return False


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
            settings.EXTENSION_CONFIG["FFC_SUB"],
            settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"],
        )
        return cls._instance


def get_ffc_client() -> FinOpsClient:
    """Get FinOps client singleton instance."""
    return _FinOpsClientFactory.get_client()
