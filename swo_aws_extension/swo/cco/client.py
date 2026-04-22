from functools import wraps
from http import HTTPStatus

import requests

from swo_aws_extension.config import Config, get_config
from swo_aws_extension.swo.base_client import OAuthSessionClient
from swo_aws_extension.swo.cco.errors import CcoHttpError, CcoNotFoundError
from swo_aws_extension.swo.cco.models import CcoContract, CreateCcoRequest, CreateCcoResponse


def wrap_http_error(func):
    """Decorator to wrap HTTP errors into CCO errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            if err.response.status_code == HTTPStatus.NOT_FOUND:
                raise CcoNotFoundError(err.response.text) from err
            raise CcoHttpError(err.response.status_code, err.response.text) from err

    return wrapper


class CcoClient(OAuthSessionClient):
    """Client to interact with the CCO (Contract Creation Online) API."""

    def __init__(self, config: Config) -> None:
        super().__init__(
            oauth_url=config.cco_oauth_url,
            client_id=config.cco_client_id,
            client_secret=config.cco_client_secret,
            audience=config.cco_audience,
            base_url=config.cco_api_base_url,
        )
        self._config = config

    @wrap_http_error
    def create_cco(self, request: CreateCcoRequest) -> CreateCcoResponse:
        """Create a CCO contract in Navision.

        Args:
            request: CCO contract creation request data.

        Returns:
            CreateCcoResponse containing the new contract number.
        """
        response = self.post(url="v1/contracts", json=request.to_api_dict())
        response.raise_for_status()
        response_json = response.json()
        contract_number = response_json["contractInsert"]["contractNumber"]
        return CreateCcoResponse(contract_number=contract_number)

    @wrap_http_error
    def get_all_contracts(self, mpa_id: str) -> list[CcoContract]:
        """Retrieve all CCO contracts for a AWS Master Payer Account.

        Args:
            mpa_id: The AWS Master Payer Account ID.

        Returns:
            List of CcoContract objects.
        """
        response = self.get(url=f"v1/contracts/all/{mpa_id}")
        response.raise_for_status()
        return [CcoContract.from_dict(contract_data) for contract_data in response.json()]

    @wrap_http_error
    def get_contract_by_id(self, cco_id: str) -> CcoContract | None:
        """Retrieve a single CCO contract by its ID.

        Args:
            cco_id: The CCO contract number.

        Returns:
            CcoContract if found, None if the contract does not exist.
        """
        response = self.get(url=f"v1/contracts/{cco_id}")
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return CcoContract.from_dict(response.json())


class _CcoClientFactory:
    """Factory for CCO client singleton."""

    _instance: CcoClient | None = None

    @classmethod
    def get_client(cls) -> CcoClient:
        """Get CCO client singleton instance."""
        if cls._instance is not None:
            return cls._instance
        cls._instance = CcoClient(config=get_config())
        return cls._instance


def get_cco_client() -> CcoClient:
    """Get CCO client singleton instance."""
    return _CcoClientFactory.get_client()
