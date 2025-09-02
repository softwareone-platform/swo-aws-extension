from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE, ORDER_TYPE_PURCHASE

from swo_aws_extension.constants import TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import ValidatePurchaseTransferWithoutOrganizationStep


def test_validate_with_all_ok(mocker, order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="123456789012\n\n123456789012\n123456789012",
        ),
        order_type=ORDER_TYPE_PURCHASE,
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch("swo_aws_extension.flows.steps.validate.set_ordering_parameter_error")
    step = ValidatePurchaseTransferWithoutOrganizationStep()
    next_step = mocker.Mock()
    client = mocker.Mock()
    step(client, context, next_step)

    next_step.assert_called_once()


def test_is_not_purchase_order(mocker, order_factory, order_parameters_factory):
    logger_mock = mocker.patch("swo_aws_extension.flows.steps.validate.logger")
    order = order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
        order_type=ORDER_TYPE_CHANGE,
    )
    context = PurchaseContext.from_order_data(order)
    step = ValidatePurchaseTransferWithoutOrganizationStep()
    next_step = mocker.Mock()
    client = mocker.Mock()
    step(client, context, next_step)
    next_step.assert_called_once_with(client, context)
    assert logger_mock.info.mock_calls[0] == mocker.call(
        "%s - Skip - Order is not a purchase",
        "ORD-0792-5000-2253-4210",
    )


def test_is_not_transfer_without_organization(mocker, order_factory, order_parameters_factory):
    logger_mock = mocker.patch("swo_aws_extension.flows.steps.validate.logger")
    order = order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value
        ),
        order_type=ORDER_TYPE_PURCHASE,
    )
    context = PurchaseContext.from_order_data(order)
    assert context.is_purchase_order() is True
    step = ValidatePurchaseTransferWithoutOrganizationStep()
    next_step = mocker.Mock()
    client = mocker.Mock()
    step(client, context, next_step)
    next_step.assert_called_once_with(client, context)
    assert logger_mock.info.mock_calls[0] == mocker.call(
        "%s - Skip - Order is not a transfer without organization",
        "ORD-0792-5000-2253-4210",
    )


def test_invalid_account_ids(
    mocker, order_factory, order_parameters_factory, mock_switch_order_status_to_query
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="164565\n5245646456",
        ),
        order_type=ORDER_TYPE_PURCHASE,
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch("swo_aws_extension.flows.steps.validate.set_ordering_parameter_error")

    step = ValidatePurchaseTransferWithoutOrganizationStep()
    next_step = mocker.Mock()
    client = mocker.Mock()
    step(client, context, next_step)
    mock_switch_order_status_to_query.assert_called_once_with(client)
    next_step.assert_not_called()


def test_no_account_ids(
    mocker, order_factory, order_parameters_factory, mock_switch_order_status_to_query
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="",
        ),
        order_type=ORDER_TYPE_PURCHASE,
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch("swo_aws_extension.flows.steps.validate.set_ordering_parameter_error")

    step = ValidatePurchaseTransferWithoutOrganizationStep()
    next_step = mocker.Mock()
    client = mocker.Mock()
    step(client, context, next_step)
    mock_switch_order_status_to_query.assert_called_once_with(client)
    next_step.assert_not_called()


def test_too_many_accounts(
    mocker, order_factory, order_parameters_factory, mock_switch_order_status_to_query
):
    logger_mock = mocker.patch("swo_aws_extension.flows.steps.validate.logger")
    accounts = [f"{i:012}" for i in range(1, 22)]
    order = order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="\n".join(accounts),
        ),
        order_type=ORDER_TYPE_PURCHASE,
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.steps.validate.set_ordering_parameter_error", return_value=order
    )

    step = ValidatePurchaseTransferWithoutOrganizationStep()
    next_step = mocker.Mock()
    client = mocker.Mock()
    step(client, context, next_step)
    mock_switch_order_status_to_query.assert_called_once_with(client)
    next_step.assert_not_called()
    assert logger_mock.info.mock_calls[0] == mocker.call(
        "%s - Querying - Transfer without organization has too many accounts",
        "ORD-0792-5000-2253-4210",
    )
