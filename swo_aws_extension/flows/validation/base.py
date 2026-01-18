import copy
import logging

from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.constants import AccountTypesEnum, OrderParametersEnum, SupportTypesEnum
from swo_aws_extension.parameters import (
    get_account_type,
    get_resold_support_plans,
    get_support_type,
    reset_ordering_parameters,
    reset_ordering_parameters_error,
    set_order_parameter_constraints,
    set_ordering_parameter_error,
)

logger = logging.getLogger(__name__)

VISIBLE_REQUIRED = {"hidden": False, "required": True, "readonly": False}
VISIBLE_OPTIONAL = {"hidden": False, "required": False, "readonly": False}
HIDDEN_OPTIONAL = {"hidden": True, "required": False, "readonly": False}

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


def _apply_support_type_constraints(order: dict, support_type: str | None) -> dict:
    """Apply parameter constraints based on support type."""
    is_resold_support = support_type == SupportTypesEnum.AWS_RESOLD_SUPPORT.value
    support_param = OrderParametersEnum.RESOLD_SUPPORT_PLANS.value
    if not is_resold_support:
        return reset_ordering_parameters(order, [support_param])

    if is_resold_support and get_resold_support_plans(order) is None:
        order = set_ordering_parameter_error(
            order,
            support_param,
            ValidationError(
                err_id="AWS002", message="Please select the resold support plans option."
            ).to_dict(),
        )
        order = set_order_parameter_constraints(
            order, OrderParametersEnum.SUPPORT_TYPE, constraints=HIDDEN_OPTIONAL
        )

    constraints = VISIBLE_OPTIONAL if is_resold_support else HIDDEN_OPTIONAL
    return set_order_parameter_constraints(order, support_param, constraints=constraints)


def update_parameters_visibility(order: dict) -> dict:
    """Updates the visibility of parameters in the given order object."""
    updated_order = copy.deepcopy(order)
    updated_order = reset_ordering_parameters_error(updated_order)

    updated_order = _apply_account_type_constraints(updated_order, get_account_type(updated_order))
    return _apply_support_type_constraints(updated_order, get_support_type(updated_order))
