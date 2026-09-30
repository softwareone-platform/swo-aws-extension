import logging
from collections.abc import Callable
from typing import Any

from mpt_api_client.exceptions import MPTError
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_agreement

from swo_aws_extension.constants import FulfillmentParametersEnum, ParamPhasesEnum

logger = logging.getLogger(__name__)

ParameterGetter = Callable[[dict[str, Any]], str | None]


def get_agreement_parameter(order: dict[str, Any], getter: ParameterGetter) -> str | None:
    """Return a fulfillment parameter of the order agreement through its getter, if any."""
    agreement = order.get("agreement") or {}
    if not agreement.get("parameters"):
        return None
    return getter(agreement)


def store_agreement_parameter(
    mpt_client: MPTClient,
    order: dict[str, Any],
    external_id: FulfillmentParametersEnum,
    parameter_value: str,
) -> bool:
    """
    Store a fulfillment parameter in the order agreement so a retried row reuses it.

    Returns whether the value was stored; a Marketplace error is logged and reported as False.
    """
    order_id = order.get("id")
    agreement_id = (order.get("agreement") or {}).get("id")
    agreement_parameters = {
        ParamPhasesEnum.FULFILLMENT.value: [
            {"externalId": external_id.value, "value": parameter_value}
        ]
    }
    try:
        update_agreement(mpt_client, agreement_id, parameters=agreement_parameters)
    except MPTError as error:
        logger.warning(
            "%s - Error - Parameter %s (%s) not stored in the agreement: %s",
            order_id,
            external_id.value,
            parameter_value,
            error,
        )
        return False
    return True
