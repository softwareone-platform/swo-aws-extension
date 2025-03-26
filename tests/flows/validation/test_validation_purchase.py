from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.validation.purchase import validate_purchase_order


def test_validate_new_account_empty_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="", account_email="", account_type=AccountTypesEnum.NEW_ACCOUNT
        )
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    assert result["parameters"]["ordering"][0]["constraints"] == {
        "hidden": False,
        "readonly": False,
        "required": True,
    }
    assert result["parameters"]["ordering"][1]["constraints"] == {
        "hidden": False,
        "readonly": False,
        "required": True,
    }
    assert not has_errors


def test_validate_new_account_with_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="account_name",
            account_email="test@aws.com",
            account_type=AccountTypesEnum.NEW_ACCOUNT,
        )
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    assert result["parameters"]["ordering"][0]["constraints"] == {
        "hidden": True,
        "readonly": False,
        "required": False,
    }
    assert result["parameters"]["ordering"][1]["constraints"] == {
        "hidden": True,
        "readonly": False,
        "required": False,
    }
    assert not has_errors
