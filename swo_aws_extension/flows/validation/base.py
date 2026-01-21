import copy
import logging

from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.constants import AccountTypesEnum, OrderParametersEnum
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
    updated_order = copy.deepcopy(order)
    updated_order = reset_ordering_parameters_error(updated_order)

    return _apply_account_type_constraints(updated_order, get_account_type(updated_order))
