import pytest

from swo_aws_extension.swo.cco.errors import SellerExternalIdNotFoundError
from swo_aws_extension.swo.cco.seller_mapper import SellerMapper


def test_map_returns_legal_entity_for_known_external_id():
    result = SellerMapper().map("US")

    assert result == "SWO_US"


def test_map_resolves_non_default_legal_entity_for_country():
    result = SellerMapper().map("ES_CPX")

    assert result == "CPX_ES"


def test_map_is_case_insensitive():
    result = SellerMapper().map("es_cpx")

    assert result == SellerMapper().map("ES_CPX")


def test_map_ww_fallback():
    result = SellerMapper().map("WW")

    assert result == "SWO_GlobalItem"


def test_map_raises_for_unknown_external_id():
    with pytest.raises(SellerExternalIdNotFoundError) as exc_info:
        SellerMapper().map("XX")

    assert exc_info.value.external_id == "XX"


def test_resolve_prefers_navision_company_code():
    seller = {
        "externalId": "XX",
        "attributes": {"navision": {"companyCode": "CPX_ES"}},
    }

    result = SellerMapper().resolve(seller)

    assert result == "CPX_ES"


def test_resolve_falls_back_to_external_id_without_attributes():
    result = SellerMapper().resolve({"externalId": "ES_CPX"})

    assert result == "CPX_ES"


@pytest.mark.parametrize(
    "attributes",
    [
        None,
        {},
        {"navision": None},
        {"navision": {}},
        {"navision": {"companyCode": ""}},
        {"navision": {"companyCode": "   "}},
    ],
)
def test_resolve_falls_back_to_external_id_when_company_code_is_blank(attributes):
    seller = {"externalId": "US", "attributes": attributes}

    result = SellerMapper().resolve(seller)

    assert result == "SWO_US"


def test_resolve_raises_without_company_code_and_unknown_external_id():
    with pytest.raises(SellerExternalIdNotFoundError) as exc_info:
        SellerMapper().resolve({"externalId": "XX"})

    assert exc_info.value.external_id == "XX"


def test_resolve_raises_when_seller_has_no_identifiers():
    with pytest.raises(SellerExternalIdNotFoundError) as exc_info:
        SellerMapper().resolve({})

    assert not exc_info.value.external_id
