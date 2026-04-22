import json
from importlib.resources import files

from swo_aws_extension.swo.cco.errors import SellerCountryNotFoundError

_SELLER_MAP: dict[str, str] = json.loads(
    files(__name__).joinpath("seller_external_id_map.json").read_text(encoding="utf-8")
)


class SellerMapper:
    """Maps seller country codes to SoftwareOne legal entity identifiers.

    The mapping is loaded once at import time from ``seller_external_id_map.json``
    co-located in the same package directory.
    """

    def map(self, seller_country: str) -> str:
        """Return the legal entity for *seller_country*.

        Args:
            seller_country: ISO country code (case-insensitive).

        Returns:
            The SoftwareOne legal entity string.

        Raises:
            SellerCountryNotFoundError: If the country code has no mapping.
        """
        key = seller_country.upper()
        try:
            return _SELLER_MAP[key]
        except KeyError:
            raise SellerCountryNotFoundError(key) from None
