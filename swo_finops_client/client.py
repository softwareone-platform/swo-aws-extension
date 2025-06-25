import logging
from datetime import UTC, datetime, timedelta
from functools import wraps
from urllib.parse import urljoin
from uuid import uuid4

import jwt
import requests
from requests import HTTPError

logger = logging.getLogger(__name__)


class FinOpsError(Exception):
    pass


class FinOpsHttpError(FinOpsError):
    def __init__(self, status_code: int, content: str):
        self.status_code = status_code
        self.content = content
        super().__init__(f"{self.status_code} - {self.content}")


class FinOpsNotFoundError(FinOpsHttpError):
    def __init__(self, content):
        super().__init__(404, content)


def wrap_http_error(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPError as e:
            if e.response.status_code == 404:
                raise FinOpsNotFoundError(e.response.json())
            else:
                raise FinOpsHttpError(e.response.status_code, e.response.json())

    return _wrapper


class FinOpsClient:
    def __init__(self, base_url, sub, secret):
        self._sub = sub
        self._secret = secret
        self._api_base_url = base_url

        self._jwt = None

    @wrap_http_error
    def create_entitlement(self, affiliate_external_id, datasource_id, name="AWS"):
        """
        Create new FinOps entitlement.
        Args:
            affiliate_external_id: The FinOps affiliate_external_id.
            datasource_id: The FinOps datasource_id.
            name: The FinOps entitlement name. Default is "AWS".

        Returns:
            Created entitlement details.

        """
        headers = self._get_headers()
        response = requests.post(
            urljoin(self._api_base_url, "entitlements"),
            json={
                "name": name,
                "affiliate_external_id": affiliate_external_id,
                "datasource_id": datasource_id,
            },
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @wrap_http_error
    def delete_entitlement(self, entitlement_id):
        """
        Delete the FinOps entitlement by ID.
        Args:
            entitlement_id: The FinOps entitlement_id.

        """
        headers = self._get_headers()
        response = requests.delete(
            urljoin(self._api_base_url, f"entitlements/{entitlement_id}"),
            headers=headers,
        )

        response.raise_for_status()

    @wrap_http_error
    def terminate_entitlement(self, entitlement_id):
        """
        Terminate the FinOps entitlement by ID.
        Args:
            entitlement_id: The FinOps entitlement_id.
        Returns:
            The terminated entitlement details.
        """
        headers = self._get_headers()
        response = requests.post(
            urljoin(self._api_base_url, f"entitlements/{entitlement_id}/terminate"),
            headers=headers,
        )

        response.raise_for_status()
        return response.json()

    @wrap_http_error
    def get_entitlement_by_datasource_id(self, datasource_id):
        """
        Get the FinOps entitlement details by datasource ID.

        Args:
            datasource_id: The FinOps datasource_id.
        Returns:
            The entitlement details if found, otherwise None.
        """
        headers = self._get_headers()
        response = requests.get(
            urljoin(self._api_base_url, f"entitlements?datasource_id={datasource_id}&limit=1"),
            headers=headers,
        )
        response.raise_for_status()
        result = response.json()
        return result["items"][0] if result["total"] > 0 else None

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self._get_auth_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Request-Id": str(uuid4()),
        }

    def _get_auth_token(self):
        if not self._jwt or self._is_token_expired():
            now = datetime.now(tz=UTC)
            self._jwt = jwt.encode(
                {
                    "sub": self._sub,
                    "exp": now + timedelta(minutes=5),
                    "nbf": now,
                    "iat": now,
                },
                self._secret,
                algorithm="HS256",
            )
        return self._jwt

    def _is_token_expired(self):
        try:
            jwt.decode(self._jwt, self._secret, algorithms=["HS256"])
            return False
        except jwt.ExpiredSignatureError:
            return True


_FFC_CLIENT = None


def get_ffc_client():
    """
    Returns an instance of the `FinOpsClient`.

    Returns:
        FinOpsClient: An instance of the `FinOpsClient`.
    """
    from django.conf import settings

    global _FFC_CLIENT
    if not _FFC_CLIENT:
        _FFC_CLIENT = FinOpsClient(
            settings.EXTENSION_CONFIG["FFC_OPERATIONS_API_BASE_URL"],
            settings.EXTENSION_CONFIG["FFC_SUB"],
            settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"],
        )
    return _FFC_CLIENT
