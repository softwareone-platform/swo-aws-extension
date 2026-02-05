from unittest.mock import MagicMock

from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderParametersEnum,
)
from swo_aws_extension.flows.validation.base import (
    validate_order,
)
from swo_aws_extension.parameters import get_ordering_parameter, set_order_parameter_constraints


def test_validate_order_orchestrates_all_steps_new_aws_environment(
    order_factory, order_parameters_factory, mocker
):
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
    order = set_order_parameter_constraints(
        order,
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value,
        constraints={"hidden": True, "required": False, "readonly": False},
    )
    new_account_instructions_param = get_ordering_parameter(
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, order
    )

    result = validate_order(mock_client, order)

    new_account_instructions_param = get_ordering_parameter(
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, result
    )
    master_payer_account_id_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
    )
    assert new_account_instructions_param["constraints"]["hidden"] is False
    assert new_account_instructions_param["constraints"]["required"] is True
    assert master_payer_account_id_param["constraints"]["hidden"] is True
    assert master_payer_account_id_param["constraints"]["required"] is False
    assert result["lines"] == [{"item": mock_items[0], "quantity": 1}]


def test_validate_order_orchestrates_all_steps_existing_aws_environment(
    order_factory, order_parameters_factory, mocker
):
    mock_client = MagicMock()
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
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

    new_account_instructions_param = get_ordering_parameter(
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, result
    )
    master_payer_account_id_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
    )
    assert new_account_instructions_param["constraints"]["hidden"] is True
    assert new_account_instructions_param["constraints"]["required"] is False
    assert master_payer_account_id_param["constraints"]["hidden"] is False
    assert result["lines"] == [{"item": mock_items[0], "quantity": 1}]


def test_validate_order_returns_error_when_new_account_instructions_visible(
    order_factory, order_parameters_factory
):
    """Test that validate_order returns error when newAccountInstructions is visible."""
    mock_client = MagicMock()
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value,
        ),
        lines=[],
    )
    order = set_order_parameter_constraints(
        order,
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value,
        constraints={"hidden": False, "required": False, "readonly": False},
    )

    result = validate_order(mock_client, order)

    new_account_instructions_param = get_ordering_parameter(
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, result
    )
    assert new_account_instructions_param["error"]["id"] == "AWS002"
