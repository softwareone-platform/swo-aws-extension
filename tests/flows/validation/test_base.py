from unittest.mock import MagicMock

from mpt_extension_sdk.mpt_http.base import MPTClient

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
        "swo_aws_extension.flows.validation.base.has_previous_order",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=mock_items,
    )
    order = set_order_parameter_constraints(
        order,
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value,
        constraints={"hidden": True, "required": False, "readonly": False},
    )
    get_ordering_parameter(OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, order)

    result = validate_order(mock_client, order)

    new_account_instructions_param = get_ordering_parameter(
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, result
    )
    master_payer_account_id_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
    )
    assert new_account_instructions_param["constraints"]["hidden"] is False
    assert new_account_instructions_param["constraints"]["required"] is False
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
        "swo_aws_extension.flows.validation.base.has_previous_order",
        return_value=False,
    )
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
    order_factory, order_parameters_factory, mocker
):
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
    mocker.patch(
        "swo_aws_extension.flows.validation.base.has_previous_order",
        return_value=False,
    )

    result = validate_order(mock_client, order)

    new_account_instructions_param = get_ordering_parameter(
        OrderParametersEnum.NEW_ACCOUNT_INSTRUCTIONS.value, result
    )
    assert new_account_instructions_param["error"]["id"] == "AWS002"


def test_validate_order_with_invalid_account_type(order_factory, order_parameters_factory, mocker):
    mock_client = MagicMock()
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type="INVALID_TYPE",
        ),
        lines=[],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.has_previous_order",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=[],
    )

    result = validate_order(mock_client, order)

    account_type_param = get_ordering_parameter(OrderParametersEnum.ACCOUNT_TYPE.value, result)
    assert account_type_param["error"]["id"] == "AWS001"


def test_validate_order_when_product_items_not_found(
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
    mocker.patch(
        "swo_aws_extension.flows.validation.base.has_previous_order",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=[],
    )

    result = validate_order(mock_client, order)

    assert result["lines"] == []


def test_validate_order_strips_whitespace_from_mpa_account(
    order_factory, order_parameters_factory, mocker
):
    mock_client = MagicMock(spec=MPTClient)
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            mpa_id="  651706759263  ",
            constraints={"hidden": None, "required": None, "readonly": None},
        ),
        lines=[],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.has_previous_order",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_product_items_by_skus",
        return_value=[{"id": "ITM-1", "name": "AWS Usage"}],
    )

    result = validate_order(mock_client, order)

    mpa_param = get_ordering_parameter(OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result)
    assert mpa_param["value"] == "651706759263"


def test_validate_order_rejects_change_order(order_factory):
    mock_client = MagicMock(spec=MPTClient)
    order = order_factory(order_type="Change")

    result = validate_order(mock_client, order)

    assert result["error"]["id"] == "AWS003"
    assert "Change orders are not supported" in result["error"]["message"]


def test_validate_termination_order_rejected_for_linked_account(order_factory, mocker):
    mock_client = MagicMock(spec=MPTClient)
    agreement_info = {
        "externalIds": {"vendor": "225989344502"},
        "subscriptions": [
            {
                "id": "SUB-MASTER-001",
                "externalIds": {"vendor": "225989344502"},
                "status": "Active",
            },
            {
                "id": "SUB-LINKED-001",
                "externalIds": {"vendor": "LINKED-111111111111"},
                "status": "Active",
            },
        ],
    }
    order = order_factory(
        order_type="Termination",
        lines=[
            {"subscription": {"id": "SUB-LINKED-001"}, "quantity": 0, "oldQuantity": 1},
        ],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.setup_client",
        return_value=MagicMock(),
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_agreement",
        return_value=agreement_info,
    )

    result = validate_order(mock_client, order)

    assert result["error"]["id"] == "AWS005"
    assert "linked-account subscriptions are not supported" in result["error"]["message"]


def test_validate_termination_order_allowed_when_master_subscription_is_terminating(
    order_factory, mocker
):
    mock_client = MagicMock(spec=MPTClient)
    agreement_info = {
        "externalIds": {"vendor": "225989344502"},
        "subscriptions": [
            {
                "id": "SUB-MASTER-001",
                "externalIds": {"vendor": "225989344502"},
                "status": "Active",
            },
        ],
    }
    order = order_factory(
        order_type="Termination",
        lines=[
            {"subscription": {"id": "SUB-MASTER-001"}, "quantity": 0, "oldQuantity": 1},
        ],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.setup_client",
        return_value=MagicMock(),
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_agreement",
        return_value=agreement_info,
    )

    result = validate_order(mock_client, order)

    assert result.get("error") is None


def test_validate_termination_order_rejected_when_no_master_subscription_in_lines(
    order_factory, mocker
):
    mock_client = MagicMock(spec=MPTClient)
    agreement_info = {
        "externalIds": {"vendor": "225989344502"},
        "subscriptions": [
            {
                "id": "SUB-MASTER-001",
                "externalIds": {"vendor": "225989344502"},
                "status": "Active",
            },
            {
                "id": "SUB-LINKED-001",
                "externalIds": {"vendor": "LINKED-111111111111"},
                "status": "Active",
            },
        ],
    }
    order = order_factory(
        order_type="Termination",
        lines=[
            {"subscription": {"id": "SUB-LINKED-001"}, "quantity": 0, "oldQuantity": 1},
            {"subscription": {"id": "SUB-MASTER-001"}, "quantity": 1, "oldQuantity": 1},
        ],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.setup_client",
        return_value=MagicMock(),
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.get_agreement",
        return_value=agreement_info,
    )

    result = validate_order(mock_client, order)

    assert result["error"]["id"] == "AWS005"


def test_validate_order_returns_order_unchanged_for_unknown_type(order_factory):
    mock_client = MagicMock(spec=MPTClient)
    order = order_factory(order_type="Unknown")

    result = validate_order(mock_client, order)

    assert result["type"] == "Unknown"
    assert result.get("error") is None
