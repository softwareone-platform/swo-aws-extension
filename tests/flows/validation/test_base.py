from unittest.mock import MagicMock

from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderParametersEnum,
)
from swo_aws_extension.flows.validation.base import (
    add_default_lines,
    update_parameters_visibility,
    validate_order,
)
from swo_aws_extension.parameters import get_ordering_parameter


def test_new_aws_environment(order_factory, order_parameters_factory):
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
    order_account_email = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value, result
    )
    assert order_account_email == {
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
        "externalId": "orderAccountEmail",
        "id": "PAR-1234-5680",
        "name": "Order Root Account Email",
        "type": "choice",
        "value": "example@example.com",
    }
    master_payer_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
    )
    assert master_payer_param == {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": "masterPayerID",
        "id": "PAR-1234-5680",
        "name": "Master Payer Account ID",
        "type": "choice",
        "value": None,
    }


def test_existing_aws_environment(order_factory, order_parameters_factory):
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
        "externalId": "masterPayerID",
        "id": "PAR-1234-5680",
        "name": "Master Payer Account ID",
        "type": "choice",
        "value": "651706759263",
    }
    order_account_name_param = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_NAME.value, result
    )
    assert order_account_name_param == {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": "orderAccountName",
        "id": "PAR-1234-5680",
        "name": "Order Account Name",
        "type": "choice",
        "value": None,
    }
    order_account_email = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value, result
    )
    assert order_account_email == {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": "orderAccountEmail",
        "id": "PAR-1234-5680",
        "name": "Order Root Account Email",
        "type": "choice",
        "value": None,
    }


def test_empty_values(order_factory, order_parameters_factory):
    order = order_factory(order_parameters=order_parameters_factory(account_type=None))

    result = update_parameters_visibility(order)

    account_type_param = get_ordering_parameter(OrderParametersEnum.ACCOUNT_TYPE.value, result)
    assert account_type_param["error"] == {
        "id": "AWS001",
        "message": "Invalid account type: None",
    }


def test_add_default_lines_success(order_factory, mocker):
    mock_client = MagicMock()
    order = order_factory(lines=[])
    mock_items = [
        {
            "id": "ITM-1234-1234-1234-0001",
            "name": "AWS Usage",
            "externalIds": {"vendor": "AWS Usage"},
        }
    ]
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=mock_items,
    )

    result = add_default_lines(mock_client, order)

    assert result["lines"] == [{"item": mock_items[0], "quantity": 1}]


def test_add_default_lines_no_product_id(caplog):
    mock_client = MagicMock()
    order = {"product": {}, "lines": []}

    with caplog.at_level("WARNING"):
        result = add_default_lines(mock_client, order)

    assert result["lines"] == []
    assert "No product ID found in order, skipping default lines" in caplog.text


def test_add_default_lines_no_items_found(order_factory, mocker):
    mock_client = MagicMock()
    order = order_factory(lines=[{"existing": "line"}])
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=[],
    )

    result = add_default_lines(mock_client, order)

    assert result["lines"] == [{"existing": "line"}]


def test_validate_order_orchestrates_all_steps(order_factory, order_parameters_factory, mocker):
    mock_client = MagicMock()
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value,
            constraints={"hidden": None, "required": None, "readonly": None},
        ),
        lines=[],
    )
    mock_items = [
        {
            "id": "ITM-1234-1234-1234-0001",
            "name": "AWS Usage",
            "externalIds": {"vendor": "AWS Usage"},
        }
    ]
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=mock_items,
    )

    result = validate_order(mock_client, order)

    order_account_name_param = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_NAME.value, result
    )
    assert order_account_name_param["constraints"]["hidden"] is False
    assert order_account_name_param["constraints"]["required"] is True
    assert result["lines"] == [{"item": mock_items[0], "quantity": 1}]
