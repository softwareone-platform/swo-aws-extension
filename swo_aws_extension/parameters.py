import copy
import functools
from typing import Any

from mpt_extension_sdk.mpt_http.utils import find_first
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.constants import (
    AccountTypesEnum,
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
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value,
        source,
    )
    return ordering_param.get("value", None)


def set_ordering_parameter_error(order: dict, param_external_id: str, error: dict) -> dict:
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

    return set_order_parameter_constraints(
        updated_order,
        param_external_id,
        constraints={
            "hidden": False,
            "required": True,
        },
    )


def get_phase(source: dict[str, Any]) -> str | None:
    """Get the phase from the fulfillment parameter or an empty string if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.PHASE.value,
        source,
    )
    return fulfillment_param.get("value", None)


def set_phase(order: dict[str, Any], phase: str) -> dict[str, Any]:
    """Set the phase on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.PHASE.value,
        updated_order,
    )
    fulfillment_param["value"] = phase
    return updated_order


def get_account_type(source: dict[str, Any]) -> str | None:
    """Get the account type from the ordering parameter or an empty string if it is not set."""
    ordering_param = get_ordering_parameter(
        OrderParametersEnum.ACCOUNT_TYPE.value,
        source,
    )
    return ordering_param.get("value", None)


def set_responsibility_transfer_id(order: dict[str, Any], transfer_id: str) -> dict[str, Any]:
    """Set the responsibility transfer ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
        updated_order,
    )
    fulfillment_param["value"] = transfer_id
    return updated_order


def get_responsibility_transfer_id(source: dict[str, Any]) -> str | None:
    """Get the Responsibility TransferID from the fulfillment parameter or None if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
        source,
    )
    return fulfillment_param.get("value", None)


def set_crm_onboard_ticket_id(order: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    """Set the CRM onboard ticket ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID.value,
        updated_order,
    )
    fulfillment_param["value"] = ticket_id
    return updated_order


def get_crm_onboard_ticket_id(source: dict[str, Any]) -> str | None:
    """Get the CRM onboard ticket ID from the fulfillment parameter or None if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID.value,
        source,
    )
    return fulfillment_param.get("value", None)


def set_crm_new_account_ticket_id(order: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    """Set the CRM new account ticket ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_NEW_ACCOUNT_TICKET_ID.value,
        updated_order,
    )
    fulfillment_param["value"] = ticket_id
    return updated_order


def get_crm_new_account_ticket_id(source: dict[str, Any]) -> str | None:
    """Get the CRM new account ticket ID from the fulfillment parameter or None if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_NEW_ACCOUNT_TICKET_ID.value,
        source,
    )
    return fulfillment_param.get("value", None)


def set_crm_customer_role_ticket_id(order: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    """Set the CRM customer role ticket ID on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_CUSTOMER_ROLE_TICKET_ID,
        updated_order,
    )
    fulfillment_param["value"] = ticket_id
    return updated_order


def get_crm_customer_role_ticket_id(source: dict[str, Any]) -> str | None:
    """Get the customer role ticket ID from the fulfillment parameter or None if it is not set."""
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CRM_CUSTOMER_ROLE_TICKET_ID,
        source,
    )
    return fulfillment_param.get("value", None)


def get_technical_contact_info(source: dict[str, Any]) -> dict:
    """Get the technical contact information from the purchase context."""
    ordering_param = get_ordering_parameter(
        OrderParametersEnum.CONTACT,
        source,
    )
    return ordering_param.get("value", {})


def get_order_account_name(source: dict[str, Any]) -> str | None:
    """Get the account name from the ordering parameter or None if it is not set."""
    ordering_param = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_NAME,
        source,
    )
    return ordering_param.get("value", None)


def get_order_account_email(source: dict[str, Any]) -> str | None:
    """Get the account email from the ordering parameter or None if it is not set."""
    ordering_param = get_ordering_parameter(
        OrderParametersEnum.ORDER_ROOT_ACCOUNT_EMAIL,
        source,
    )
    return ordering_param.get("value", None)


def set_order_parameter_constraints(
    order: dict, param_external_id: str, *, constraints: dict
) -> dict:
    """Sets ordering parameter constraints."""
    updated_order = copy.deepcopy(order)
    parameter_to_change = get_ordering_parameter(
        param_external_id,
        updated_order,
    )
    updated_constraints = parameter_to_change.get("constraints", {}) or {}
    updated_constraints.update(constraints)
    parameter_to_change["constraints"] = updated_constraints

    return updated_order


def set_order_parameter_value(order: dict, parameter_id: str, parameter_value: Any) -> dict:
    """Set the value of a parameter in the order."""
    updated_order = copy.deepcopy(order)
    order_param = get_ordering_parameter(
        parameter_id,
        updated_order,
    )
    order_param["value"] = parameter_value

    return updated_order


def reset_ordering_parameters(order: dict, list_parameters: list) -> dict:
    """Reset the ordering parameters to None and hide/make them readonly/not required."""
    updated_order = copy.deepcopy(order)
    for parameter_id in list_parameters:
        updated_order = set_order_parameter_value(updated_order, parameter_id, None)
        updated_order = set_order_parameter_constraints(
            updated_order,
            parameter_id,
            constraints={"hidden": True, "required": False, "readonly": True},
        )

    return updated_order


def update_parameters_visibility(order: dict) -> dict:
    """Updates the visibility of parameters in the given order object."""
    updated_order = copy.deepcopy(order)
    updated_order = reset_ordering_parameters_error(updated_order)
    account_type = get_account_type(updated_order)
    if account_type == AccountTypesEnum.NEW_AWS_ENVIRONMENT.value:
        updated_order = set_order_parameter_constraints(
            updated_order,
            OrderParametersEnum.ORDER_ACCOUNT_NAME.value,
            constraints={"hidden": False, "required": True, "readonly": False},
        )
        updated_order = set_order_parameter_constraints(
            updated_order,
            OrderParametersEnum.ORDER_ROOT_ACCOUNT_EMAIL.value,
            constraints={"hidden": False, "required": True, "readonly": False},
        )
        updated_order = reset_ordering_parameters(
            updated_order, [OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value]
        )
    elif account_type == AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value:
        updated_order = set_order_parameter_constraints(
            updated_order,
            OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value,
            constraints={"hidden": False, "required": True, "readonly": False},
        )
        updated_order = reset_ordering_parameters(
            updated_order,
            [
                OrderParametersEnum.ORDER_ACCOUNT_NAME.value,
                OrderParametersEnum.ORDER_ROOT_ACCOUNT_EMAIL.value,
            ],
        )
    else:
        updated_order = set_ordering_parameter_error(
            updated_order,
            OrderParametersEnum.ACCOUNT_TYPE.value,
            ValidationError(
                err_id="AWS001", message=f"Invalid account type: {account_type}"
            ).to_dict(),
        )

    return updated_order


def reset_ordering_parameters_error(order: dict) -> dict:
    """Reset errors for all ordering parameters."""
    updated_order = copy.deepcopy(order)

    for order_param in updated_order["parameters"][ParamPhasesEnum.ORDERING.value]:
        order_param["error"] = None

    return updated_order


def set_customer_roles_deployed(order: dict, deployed: str) -> dict:
    """Set the customer roles deployed flag on the fulfillment parameters."""
    updated_order = copy.deepcopy(order)
    fulfillment_param = get_fulfillment_parameter(
        FulfillmentParametersEnum.CUSTOMER_ROLES_DEPLOYED.value,
        updated_order,
    )
    fulfillment_param["value"] = deployed
    return updated_order
