from swo_aws_extension.constants import AccountTypesEnum, OrderParametersEnum
from swo_aws_extension.parameters import (
    get_ordering_parameter,
    reset_ordering_parameters_error,
    update_parameters_visibility,
)


class TestUpdateParametersVisibility:
    def test_new_aws_environment(self, order_factory, order_parameters_factory):
        """Test update params visibility for a new AWS environment."""
        order = order_factory(
            order_parameters=order_parameters_factory(
                account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value,
                constraints={"hidden": None, "required": None, "readonly": None},
            )
        )

        result = update_parameters_visibility(order)

        order_account_name_param = get_ordering_parameter(
            OrderParametersEnum.ORDER_ACCOUNT_NAME.value, result
        )
        assert order_account_name_param == {
            "constraints": {"hidden": False, "readonly": False, "required": True},
            "error": None,
            "externalId": "orderAccountName",
            "id": "PAR-1234-5680",
            "name": "Order Account Name",
            "type": "choice",
            "value": "Order Account Name",
        }
        order_root_account_email = get_ordering_parameter(
            OrderParametersEnum.ORDER_ROOT_ACCOUNT_EMAIL.value, result
        )
        assert order_root_account_email == {
            "constraints": {"hidden": False, "readonly": False, "required": True},
            "error": None,
            "externalId": "orderRootAccountEmail",
            "id": "PAR-1234-5680",
            "name": "Order Root Account Email",
            "type": "choice",
            "value": "example@example.com",
        }
        master_payer_param = get_ordering_parameter(
            OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
        )
        assert master_payer_param == {
            "constraints": {"hidden": True, "readonly": True, "required": False},
            "error": None,
            "externalId": "masterPayerId",
            "id": "PAR-1234-5680",
            "name": "Master Payer Account ID",
            "type": "choice",
            "value": None,
        }

    def test_existing_aws_environment(self, order_factory, order_parameters_factory):
        """Test update params visibility for an existing AWS environment."""
        order = order_factory(
            order_parameters=order_parameters_factory(
                account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
                constraints={"hidden": None, "required": None, "readonly": None},
            )
        )

        result = update_parameters_visibility(order)

        master_payer_param = get_ordering_parameter(
            OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
        )
        assert master_payer_param == {
            "constraints": {"hidden": False, "readonly": False, "required": True},
            "error": None,
            "externalId": "masterPayerId",
            "id": "PAR-1234-5680",
            "name": "Master Payer Account ID",
            "type": "choice",
            "value": "651706759263",
        }
        order_account_name_param = get_ordering_parameter(
            OrderParametersEnum.ORDER_ACCOUNT_NAME.value, result
        )
        assert order_account_name_param == {
            "constraints": {"hidden": True, "readonly": True, "required": False},
            "error": None,
            "externalId": "orderAccountName",
            "id": "PAR-1234-5680",
            "name": "Order Account Name",
            "type": "choice",
            "value": None,
        }
        order_root_account_email = get_ordering_parameter(
            OrderParametersEnum.ORDER_ROOT_ACCOUNT_EMAIL.value, result
        )
        assert order_root_account_email == {
            "constraints": {"hidden": True, "readonly": True, "required": False},
            "error": None,
            "externalId": "orderRootAccountEmail",
            "id": "PAR-1234-5680",
            "name": "Order Root Account Email",
            "type": "choice",
            "value": None,
        }

    def test_empty_values(self, order_factory, order_parameters_factory):
        """Test the update_parameters_visibility function when parameter values are empty."""
        order = order_factory(order_parameters=order_parameters_factory(account_type=None))

        result = update_parameters_visibility(order)

        account_type_param = get_ordering_parameter(OrderParametersEnum.ACCOUNT_TYPE.value, result)
        assert account_type_param["error"] == {
            "id": "AWS001",
            "message": "Invalid account type: None",
        }


def test_reset_ordering_parameters_error(order_factory, order_parameters_factory):
    """Test that reset_ordering_parameters_error clears all parameter errors."""
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        )
    )

    # Set an error on a parameter
    order["parameters"]["ordering"][0]["error"] = {
        "err_id": "TEST001",
        "message": "Test error",
    }

    result = reset_ordering_parameters_error(order)

    # Verify all parameters have error set to None
    for ordering_params in result["parameters"]["ordering"]:
        assert ordering_params["error"] is None
