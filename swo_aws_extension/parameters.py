import copy
import functools
from typing import Any

from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    OrderParametersEnum,
    ParamPhasesEnum,
)


def get_parameter(parameter_phase: str, source: dict[str, Any], param_external_id: str) -> dict:
    """Returns a parameter of a given phase by its external identifier."""
    return find_first(
        lambda phase: phase["externalId"] == param_external_id,
        source["parameters"][parameter_phase],
        default={},
    )


get_ordering_parameter = functools.partial(get_parameter, ParamPhasesEnum.ORDERING.value)

get_fulfillment_parameter = functools.partial(get_parameter, ParamPhasesEnum.FULFILLMENT.value)


def get_phase(source: dict[str, Any]) -> str | None:
    """Get the phase from the fulfillment parameter or an empty string if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        source,
        FulfillmentParametersEnum.PHASE,
    )
    return fulfillment_param.get("value", None)


def set_phase(order: dict[str, Any], phase: str) -> dict[str, Any]:
    """Set the phase on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.PHASE,
    )
    fulfillment_param["value"] = phase
    return updated_order


def get_pm_account_id(source: dict[str, Any]) -> str | None:
    """Get the PM Account ID from the fulfillment parameter or an empty string if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        source,
        FulfillmentParametersEnum.PM_ACCOUNT_ID,
    )
    return fulfillment_param.get("value", None)


def set_pm_account_id(order: dict[str, Any], pm_account_id: str) -> dict[str, Any]:
    """Set the PM Account ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.PM_ACCOUNT_ID,
    )
    fulfillment_param["value"] = pm_account_id
    return updated_order


def get_account_type(source: dict[str, Any]) -> str | None:
    """Get the account type from the ordering parameter or an empty string if it is not set."""
    ordering_param = get_ordering_parameter(
        source,
        OrderParametersEnum.ACCOUNT_TYPE,
    )
    return ordering_param.get("value", None)
