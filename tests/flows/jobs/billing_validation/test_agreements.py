from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_validation.agreements import extract_discounts


def _agreement():
    return {
        "id": "AGR-7838-5542-4358",
        "externalIds": {"vendor": "539247447083"},
        "authorization": {"id": "AUT-2837-7325"},
        "parameters": {
            "fulfillment": [
                {"externalId": "channelHandshakeApproved", "value": "yes"},
                {"externalId": "serviceDiscount", "value": "62.5"},
                {"externalId": "serviceDiscountType", "value": "SPP_DISCOUNT"},
                {"externalId": "supportDiscount", "value": ""},
                {"externalId": "plsDiscount", "value": "10"},
            ],
            "ordering": [{"externalId": "supportType", "value": "PartnerLedSupport"}],
        },
    }


def test_extract_discounts_reads_agreement_parameters():
    result = extract_discounts(_agreement())

    assert (result.agreement_id, result.mpa, result.authorization_id) == (
        "AGR-7838-5542-4358",
        "539247447083",
        "AUT-2837-7325",
    )
    assert (result.service_discount, result.support_discount, result.pls_discount) == (
        Decimal("62.5"),
        Decimal(0),
        Decimal(10),
    )
    assert result.is_pls
    assert result.handshake_approved


def test_extract_discounts_defaults_when_parameters_are_missing():
    agreement = {"id": "AGR-1", "parameters": {"fulfillment": [], "ordering": []}}

    result = extract_discounts(agreement)

    assert result.service_discount == Decimal(0)
    assert not result.handshake_approved
    assert not result.is_pls
    assert not result.is_resold_support
