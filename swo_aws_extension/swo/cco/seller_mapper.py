import json
from importlib.resources import files
from typing import Any

from swo_aws_extension.swo.cco.errors import SellerExternalIdNotFoundError

_SELLER_MAP: dict[str, str] = json.loads(
    files(__name__).joinpath("seller_external_id_map.json").read_text(encoding="utf-8")
)


def _get_navision_company_code(seller: dict[str, Any]) -> str:
    attributes = seller.get("attributes") or {}
    navision = attributes.get("navision") or {}
    return (navision.get("companyCode") or "").strip()


class SellerMapper:
    """Resolves the SoftwareOne legal entity (Navision company) of a Marketplace seller.

    The Navision company code stored in the seller ``attributes.navision.companyCode``
    is used when present. Otherwise the seller ``externalId`` (for example ``ES`` or
    ``ES_CPX``) is looked up in ``seller_external_id_map.json``, loaded once at import
    time from the same package directory. The seller address country is never used,
    because a country can have several SoftwareOne legal entities.
    """

    def resolve(self, seller: dict[str, Any]) -> str:
        """Return the legal entity for a Marketplace *seller* object.

        Args:
            seller: Seller dict as embedded in the order (``externalId``, ``attributes``).

        Returns:
            The SoftwareOne legal entity string.

        Raises:
            SellerExternalIdNotFoundError: If the seller has no Navision company code and
                its external ID has no mapping.
        """
        company_code = _get_navision_company_code(seller)
        if company_code:
            return company_code
        return self.map(seller.get("externalId") or "")

    def map(self, seller_external_id: str) -> str:
        """Return the legal entity for *seller_external_id*.

        Args:
            seller_external_id: Marketplace seller external ID (case-insensitive).

        Returns:
            The SoftwareOne legal entity string.

        Raises:
            SellerExternalIdNotFoundError: If the external ID has no mapping.
        """
        key = seller_external_id.upper()
        try:
            return _SELLER_MAP[key]
        except KeyError:
            raise SellerExternalIdNotFoundError(key) from None
