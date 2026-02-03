import copy
import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_product_items_by_skus
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.constants import AWS_ITEMS_SKUS, AccountTypesEnum, OrderParametersEnum
from swo_aws_extension.parameters import (
    get_account_type,
    reset_ordering_parameters,
    reset_ordering_parameters_error,
    set_order_parameter_constraints,
    set_ordering_parameter_error,
)

logger = logging.getLogger(__name__)

VISIBLE_REQUIRED = {"hidden": False, "required": True, "readonly": False}


ACCOUNT_TYPE_CONFIG = {
    AccountTypesEnum.NEW_AWS_ENVIRONMENT.value: {
        "visible_params": [
            OrderParametersEnum.ORDER_ACCOUNT_NAME.value,
            OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value,
        ],
        "reset_params": [OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value],
    },
    AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value: {
        "visible_params": [OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value],
        "reset_params": [
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
        order = set_order_parameter_constraints(order, param_property, constraints=VISIBLE_REQUIRED)

    return reset_ordering_parameters(order, config["reset_params"])


def update_parameters_visibility(order: dict) -> dict:
    """Updates the visibility of parameters in the given order object."""
    updated_order = reset_ordering_parameters_error(order)
    return _apply_account_type_constraints(updated_order, get_account_type(updated_order))


def add_default_lines(client: MPTClient, order: dict) -> dict:
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
    if not product_id:
        logger.warning("No product ID found in order, skipping default lines")
        return order

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


def validate_order(client: MPTClient, order: dict) -> dict:
    """
    Main validation function that orchestrates all validation steps.

    This function performs the following steps:
    1. Creates a deep copy of the order to avoid mutations
    2. Updates parameter visibility based on account type
    3. Adds default line items to the order

    Args:
        client: MPT client for API calls.
        order: The order dictionary to validate.

    Returns:
        The validated order with updated parameters and default lines.
    """
    validated_order = copy.deepcopy(order)
    validated_order = update_parameters_visibility(validated_order)
    return add_default_lines(client, validated_order)
