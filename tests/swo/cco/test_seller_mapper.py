import pytest

from swo_aws_extension.swo.cco.errors import SellerCountryNotFoundError
from swo_aws_extension.swo.cco.seller_mapper import SellerMapper


def test_map_returns_legal_entity_for_known_country():
    result = SellerMapper().map("US")

    assert result == "SWO_US"


def test_map_is_case_insensitive():
    result = SellerMapper().map("us")

    assert result == SellerMapper().map("US")


def test_map_ww_fallback():
    result = SellerMapper().map("WW")

    assert result == "SWO_GlobalItem"


def test_map_raises_for_unknown_country():
    with pytest.raises(SellerCountryNotFoundError) as exc_info:
        SellerMapper().map("XX")

    assert exc_info.value.country == "XX"
