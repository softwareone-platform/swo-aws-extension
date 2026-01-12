from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.parameters import (
    reset_ordering_parameters_error,
)


def test_reset_ordering_parameters_error(order_factory, order_parameters_factory):
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
