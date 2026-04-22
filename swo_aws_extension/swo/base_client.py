import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from swo_aws_extension.swo.auth import get_auth_token

TIMEOUT = 60
TOKEN_EXPIRY_BUFFER = 60


class OAuthSessionClient(requests.Session):
    """Base HTTP client with OAuth token refresh and URL normalization.

    Subclasses must call ``super().__init__(...)`` with the required
    OAuth parameters.  The base class takes care of:

    * Refreshing the bearer token transparently before every request.
    * Stripping a leading ``/`` from relative URLs and joining them
      with *base_url*.
    * Setting a default request timeout.
    """

    def __init__(
        self,
        oauth_url: str,
        client_id: str,
        client_secret: str,
        audience: str,
        base_url: str,
    ) -> None:
        super().__init__()
        self._oauth_url = oauth_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._audience = audience
        self._token_expiry: float | None = None
        self.base_url = self._normalize_base_url(base_url)

    def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> requests.Response:
        """Makes HTTP request with automatic token refresh."""
        parsed = urlparse(url)
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"Absolute URLs are not allowed: {url!r}")
        self._refresh_token_if_expired()
        if url and url[0] == "/":
            url = url[1:]
        full_url = urljoin(self.base_url, url)
        kwargs.setdefault("timeout", TIMEOUT)
        return super().request(method, full_url, *args, **kwargs)

    def _refresh_token_if_expired(self) -> None:
        if self._token_expiry is None or time.time() >= (self._token_expiry - TOKEN_EXPIRY_BUFFER):
            token = get_auth_token(
                endpoint=self._oauth_url,
                client_id=self._client_id,
                client_secret=self._client_secret,
                scope=None,
                audience=self._audience,
            )
            self._token_expiry = time.time() + token["expires_in"]
            self.headers.update(self._build_auth_headers(token))

    def _build_auth_headers(self, token: dict[str, Any]) -> dict[str, str]:
        return {
            "User-Agent": "swo-extensions/1.0",
            "Authorization": f"Bearer {token['access_token']}",
        }

    def _normalize_base_url(self, base_url: str) -> str:
        return base_url if base_url.endswith("/") else f"{base_url}/"
