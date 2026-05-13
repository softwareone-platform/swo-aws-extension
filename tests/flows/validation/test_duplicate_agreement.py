from unittest.mock import MagicMock

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderParametersEnum,
)
from swo_aws_extension.flows.validation.base import validate_order
from swo_aws_extension.parameters import get_ordering_parameter


def test_validate_order_blocks_purchase_when_active_agreement_exists_for_licensee(
    order_factory, order_parameters_factory, mocker
):
    mock_client = MagicMock(spec=MPTClient)
    order = order_factory(
        order_type="Purchase",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
        ),
        lines=[],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_previous_order",
        return_value={"id": "AGR-0001"},
    )

    result = validate_order(mock_client, order)

    account_type_param = get_ordering_parameter(OrderParametersEnum.ACCOUNT_TYPE.value, result)
    assert account_type_param["error"]["id"] == "AWS004"


def test_validate_order_allows_purchase_when_no_existing_agreement_for_licensee(
    order_factory, order_parameters_factory, mocker
):
    mock_client = MagicMock(spec=MPTClient)
    order = order_factory(
        order_type="Purchase",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            constraints={"hidden": None, "required": None, "readonly": None},
        ),
        lines=[],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_previous_order",
        return_value=None,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=[{"id": "ITM-1", "name": "AWS Usage"}],
    )

    result = validate_order(mock_client, order)

    account_type_param = get_ordering_parameter(OrderParametersEnum.ACCOUNT_TYPE.value, result)
    assert account_type_param.get("error") is None


def test_validate_order_skips_duplicate_check_for_non_purchase_orders(
    order_factory, order_parameters_factory, mocker
):
    mock_client = MagicMock(spec=MPTClient)
    order = order_factory(
        order_type="Change",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            constraints={"hidden": None, "required": None, "readonly": None},
        ),
        lines=[],
    )
    mock_get_previous = mocker.patch(
        "swo_aws_extension.flows.validation.base.get_previous_order",
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=[{"id": "ITM-1", "name": "AWS Usage"}],
    )

    validate_order(mock_client, order)  # act

    assert not mock_get_previous.called
