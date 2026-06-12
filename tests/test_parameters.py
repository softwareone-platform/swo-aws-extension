from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.parameters import (
    get_termination_date,
    reset_ordering_parameters_error,
    set_termination_date,
)


def test_get_termination_date(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(termination_date="2026-12-31")
    )

    result = get_termination_date(order)

    assert result == "2026-12-31"


def test_get_termination_date_not_set():
    source = {"parameters": {"fulfillment": []}}

    result = get_termination_date(source)

    assert result is None


def test_set_termination_date(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(termination_date="")
    )

    result = set_termination_date(order, "2026-12-31")

    assert get_termination_date(result) == "2026-12-31"


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
