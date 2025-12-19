import copy
import functools
from typing import Any

from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    OrderParametersEnum,
    ParamPhasesEnum,
)


def get_parameter(parameter_phase: str, param_external_id: str, source: dict[str, Any]) -> dict:
    """Returns a parameter of a given phase by its external identifier."""
    return find_first(
        lambda elem: elem.get("externalId") == param_external_id,
        source["parameters"][parameter_phase],
        default={},
    )


get_ordering_parameter = functools.partial(get_parameter, ParamPhasesEnum.ORDERING.value)

get_fulfillment_parameter = functools.partial(get_parameter, ParamPhasesEnum.FULFILLMENT.value)
get_responsibility_transfer_id = functools.partial(
    get_fulfillment_parameter, FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID
)


def get_phase(source: dict[str, Any]) -> str | None:
    """Get the phase from the fulfillment parameter or an empty string if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.PHASE,
        source,
    )
    return fulfillment_param.get("value", None)


def set_phase(order: dict[str, Any], phase: str) -> dict[str, Any]:
    """Set the phase on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.PHASE,
        updated_order,
    )
    fulfillment_param["value"] = phase
    return updated_order


def get_account_type(source: dict[str, Any]) -> str | None:
    """Get the account type from the ordering parameter or an empty string if it is not set."""
    ordering_param = get_ordering_parameter(
        OrderParametersEnum.ACCOUNT_TYPE,
        source,
    )
    return ordering_param.get("value", None)
