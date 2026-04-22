import threading
from collections.abc import Callable
from functools import wraps
from http import HTTPStatus

import requests

from swo_aws_extension.config import Config, get_config
from swo_aws_extension.swo.base_client import OAuthSessionClient
from swo_aws_extension.swo.cco.errors import CcoError, CcoHttpError, CcoNotFoundError
from swo_aws_extension.swo.cco.models import CcoContract, CreateCcoRequest, CreateCcoResponse


def _cco_http_error_from(err: requests.HTTPError) -> CcoHttpError:
    """Convert a requests.HTTPError into a CcoHttpError, handling absent response."""
    if err.response is None:
        return CcoHttpError(0, str(err))
    return CcoHttpError(err.response.status_code, err.response.text)


def _raise_cco_error(err: requests.HTTPError) -> None:
    """Raise a domain-specific CCO error from an HTTPError."""
    if err.response is not None and err.response.status_code == HTTPStatus.NOT_FOUND:
        raise CcoNotFoundError(err.response.text) from err
    raise _cco_http_error_from(err) from err


def wrap_http_error[**FuncParams, ReturnT](
    func: Callable[FuncParams, ReturnT],
) -> Callable[FuncParams, ReturnT]:
    """Decorator to wrap HTTP errors into CCO errors."""

    @wraps(func)
    def wrapper(*args: FuncParams.args, **kwargs: FuncParams.kwargs) -> ReturnT:
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            _raise_cco_error(err)

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
        self._config = config  # reserved for future configuration access

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
        try:
            response_json = response.json()
        except ValueError as exc:
            raise CcoError(
                f"Invalid JSON in CCO API response ({response.status_code}): {response.text!r}"
            ) from exc
        if (
            not isinstance(response_json, dict)
            or not isinstance(response_json.get("contractInsert"), dict)
            or "contractNumber" not in response_json["contractInsert"]
        ):
            raise CcoError(f"Unexpected response payload from CCO API: {response_json}")
        contract_number = response_json["contractInsert"]["contractNumber"]
        if not isinstance(contract_number, str) or not contract_number.strip():
            raise CcoError(f"Unexpected response payload from CCO API: {response_json}")
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
        try:
            contracts = response.json()
        except ValueError as exc:
            raise CcoError(
                f"Invalid JSON in CCO API response for MPA '{mpa_id}'"
                f" ({response.status_code}): {response.text!r}"
            ) from exc
        if not isinstance(contracts, list):
            raise CcoError(
                f"Unexpected response payload for MPA '{mpa_id}': expected list, got {contracts!r}"
            )
        for contract_entry in contracts:
            if not isinstance(contract_entry, dict) or not contract_entry.get("contractNumber"):
                raise CcoError(f"Malformed contract item for MPA '{mpa_id}': {contract_entry!r}")
        return [CcoContract.from_dict(contract_data) for contract_data in contracts]

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
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            raise _cco_http_error_from(err) from err
        try:
            contract_dict = response.json()
        except ValueError as exc:
            raise CcoError(
                f"Unexpected response payload for contract '{cco_id}': {response.text!r}"
            ) from exc
        if not isinstance(contract_dict, dict) or not contract_dict.get("contractNumber"):
            raise CcoError(
                f"Unexpected response payload for contract '{cco_id}': {contract_dict!r}"
            )
        return CcoContract.from_dict(contract_dict)


class _CcoClientFactory:
    """Factory for CCO client singleton."""

    _instance: CcoClient | None = None
    _init_lock: threading.Lock = threading.Lock()

    @classmethod
    def get_client(cls) -> CcoClient:
        """Get CCO client singleton instance."""
        if cls._instance is not None:
            return cls._instance
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = CcoClient(config=get_config())
        return cls._instance


def get_cco_client() -> CcoClient:
    """Get CCO client singleton instance."""
    return _CcoClientFactory.get_client()
