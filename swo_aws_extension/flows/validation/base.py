import copy
import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_product_items_by_skus
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.constants import AWS_ITEMS_SKUS, AccountTypesEnum, OrderParametersEnum
from swo_aws_extension.parameters import (
    get_account_type,
    get_ordering_parameter,
    reset_ordering_parameters,
    reset_ordering_parameters_error,
    set_order_parameter_constraints,
    set_ordering_parameter_error,
)

logger = logging.getLogger(__name__)

VISIBLE_REQUIRED = {"hidden": False, "required": True, "readonly": False}
VISIBLE = {"hidden": False, "required": False, "readonly": False}


ACCOUNT_TYPE_CONFIG = {
    AccountTypesEnum.NEW_AWS_ENVIRONMENT.value: {
        "visible_params": [
            OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value,
        ],
        "required_params": [],
        "reset_params": [
            OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value,
            OrderParametersEnum.TECHNICAL_CONTACT_INFO.value,
            OrderParametersEnum.CONNECT_AWS_BILLING_ACCOUNT.value,
            OrderParametersEnum.CONTACT.value,
        ],
    },
    AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value: {
        "visible_params": [
            OrderParametersEnum.TECHNICAL_CONTACT_INFO.value,
            OrderParametersEnum.CONNECT_AWS_BILLING_ACCOUNT.value,
        ],
        "required_params": [
            OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value,
            OrderParametersEnum.CONTACT.value,
        ],
        "reset_params": [
            OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value,
            OrderParametersEnum.ORDER_ACCOUNT_NAME.value,
            OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value,
        ],
    },
}


def _apply_account_type_constraints(order: dict, account_type: str | None) -> dict:
    """Apply parameter constraints based on account type configuration."""
    config = ACCOUNT_TYPE_CONFIG.get(account_type)
    if not config:
        return set_ordering_parameter_error(
            order,
            OrderParametersEnum.ACCOUNT_TYPE.value,
            ValidationError(
                err_id="AWS001", message=f"Invalid account type: {account_type}"
            ).to_dict(),
        )

    for param_property in config["visible_params"]:
        order = set_order_parameter_constraints(order, param_property, constraints=VISIBLE)

    for param_property in config["required_params"]:
        order = set_order_parameter_constraints(order, param_property, constraints=VISIBLE_REQUIRED)

    return reset_ordering_parameters(order, config["reset_params"])


def _add_default_lines(client: MPTClient, order: dict) -> dict:
    """
    Add default line items to the order based on product SKUs.

    Retrieves product items by SKUs and adds them as lines to the order
    with quantity 1 each.

    Args:
        client: MPT client for API calls.
        order: The order dictionary to add lines to.

    Returns:
        The order with default lines added.
    """
    product_id = order.get("product", {}).get("id", "")
    aws_items = get_product_items_by_skus(client, product_id, AWS_ITEMS_SKUS)
    if not aws_items:
        logger.error(
            "Failed to get product items with SKUs %s for product %s",
            AWS_ITEMS_SKUS,
            product_id,
        )
        return order

    order["lines"] = [{"item": aws_item, "quantity": 1} for aws_item in aws_items]
    return order


def _is_parameter_visible(order: dict, param_external_id: str) -> bool:
    """Check if a parameter is visible (not hidden) in the order."""
    parameter = get_ordering_parameter(param_external_id, order)
    constraints = parameter.get("constraints", {}) or {}
    return not constraints.get("hidden", True)


def _validate_new_account_constraints(order: dict) -> dict | None:
    """
    Validate that newAccountInstructions parameter is not visible.

    If the parameter is visible, returns the order with an error set.
    Otherwise, returns None to indicate validation passed.
    """
    if get_account_type(order) != AccountTypesEnum.NEW_AWS_ENVIRONMENT.value:
        return None

    if _is_parameter_visible(order, OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value):
        return set_ordering_parameter_error(
            order,
            OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value,
            ValidationError(
                err_id="AWS002",
                message=(
                    "You should follow the instructions provided in the new account "
                    "instructions parameter and get back to select existing AWS "
                    "account type"
                ),
            ).to_dict(),
        )
    return None


def validate_order(client: MPTClient, order: dict) -> dict:
    """
    Main validation function that orchestrates all validation steps.

    This function performs the following steps:
    1. Creates a deep copy of the order to avoid mutations
    2. Validates that newAccountInstructions is not visible
    3. Updates parameter visibility based on account type
    4. Adds default line items to the order

    Args:
        client: MPT client for API calls.
        order: The order dictionary to validate.

    Returns:
        The validated order with updated parameters and default lines.
    """
    validated_order = copy.deepcopy(order)
    validated_order = reset_ordering_parameters_error(validated_order)
    error_order = _validate_new_account_constraints(validated_order)
    if error_order:
        return error_order
    validated_order = _apply_account_type_constraints(
        validated_order, get_account_type(validated_order)
    )
    return _add_default_lines(client, validated_order)
