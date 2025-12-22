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


def get_mpa_account_id(source: dict[str, Any]) -> str | None:
    """Get the Master Payer Account ID from the ordering parameter or None if it is not set."""
    ordering_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
        source,
    )
    return ordering_param.get("value", None)


def set_ordering_parameter_error(order, param_external_id, error):
    """
    Set a validation error on an ordering parameter.

    Args:
        order (dict): The order that contains the parameter.
        param_external_id (str): The external identifier of the parameter.
        error (dict): The error (id, message) that must be set.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    parameter = get_ordering_parameter(
        param_external_id,
        updated_order,
    )
    parameter["error"] = error
    parameter["constraints"] = {
        "hidden": False,
        "required": True,
    }
    return updated_order


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


def set_responsibility_transfer_id(order: dict[str, Any], transfer_id: str) -> dict[str, Any]:
    """Set the responsibility transfer ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID,
        updated_order,
    )
    fulfillment_param["value"] = transfer_id
    return updated_order


def get_responsibility_transfer_id(source: dict[str, Any]) -> str | None:
    """Get the Responsibility TransferID from the fulfillment parameter or None if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID,
        source,
    )
    return fulfillment_param.get("value", None)


def set_crm_onboard_ticket_id(order: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    """Set the CRM onboard ticket ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID,
        updated_order,
    )
    fulfillment_param["value"] = ticket_id
    return updated_order


def get_crm_onboard_ticket_id(source: dict[str, Any]) -> str | None:
    """Get the CRM onboard ticket ID from the fulfillment parameter or None if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID,
        source,
    )
    return fulfillment_param.get("value", None)
