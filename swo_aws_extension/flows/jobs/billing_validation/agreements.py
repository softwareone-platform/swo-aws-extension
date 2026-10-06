"""Read the discount parameters of a platform agreement."""

from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO, ChannelHandshakeDeployed
from swo_aws_extension.flows.jobs.billing_validation.models import (
    AgreementDiscounts,
    AgreementNames,
)
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_pls_discount,
    get_service_discount,
    get_service_discount_type,
    get_support_discount,
    get_support_type,
)


def _percentage(raw_value: str | None) -> Decimal:
    if not raw_value:
        return DEC_ZERO
    return Decimal(str(raw_value))


def extract_discounts(agreement: dict) -> AgreementDiscounts:
    """Read the discount configuration from an agreement payload."""
    return AgreementDiscounts(
        agreement_id=agreement.get("id", ""),
        mpa=agreement.get("externalIds", {}).get("vendor", ""),
        authorization_id=agreement.get("authorization", {}).get("id", ""),
        handshake_approved=(
            get_channel_handshake_approval_status(agreement) == ChannelHandshakeDeployed.YES
        ),
        support_type=get_support_type(agreement),
        service_discount=_percentage(get_service_discount(agreement)),
        service_discount_type=get_service_discount_type(agreement),
        support_discount=_percentage(get_support_discount(agreement)),
        pls_discount=_percentage(get_pls_discount(agreement)),
    )


def extract_info(agreement: dict, authorization_name: str = "") -> AgreementNames:
    """Read the agreement, client and authorization names from an agreement payload.

    The authorization name comes from the authorization being processed when known,
    otherwise from the reference embedded in the agreement.
    """
    return AgreementNames(
        agreement_name=agreement.get("name", ""),
        client_name=agreement.get("client", {}).get("name", ""),
        authorization_name=authorization_name or agreement.get("authorization", {}).get("name", ""),
    )
