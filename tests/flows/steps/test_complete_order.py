import copy

import pytest
from mpt_extension_sdk.flows.context import (
    ORDER_TYPE_CHANGE,
    ORDER_TYPE_PURCHASE,
    ORDER_TYPE_TERMINATION,
)
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderCompletedTemplateEnum,
    PhasesEnum,
    SupportTypesEnum,
    TransferTypesEnum,
)
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_COMPLETED,
    ChangeContext,
    InitialAWSContext,
)
from swo_aws_extension.flows.steps import (
    CompleteChangeOrderStep,
    CompleteOrderStep,
    CompletePurchaseOrderStep,
)


def test_complete_order(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory(phase=""))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    template_data = {"id": "TPL-964-112", "name": OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS}
    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=template_data,
    )

    def dummy_complete_order(
        _client,
        _order_id,
        template,
        parameters,
    ):
        new_order = copy.deepcopy(order)
        new_order["template"] = template
        new_order["parameters"] = parameters
        return new_order

    mocked_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        side_effect=dummy_complete_order,
    )

    complete_order = CompleteOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock,
        "PRD-1111-1111",
        "Completed",
        OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS,
    )
    mocked_complete_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        parameters=context.order["parameters"],
        template=template_data,
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_purchase_order_phase(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED)
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    template_data = {"id": "TPL-964-112", "name": "template-name"}

    def update_template_side_effect(client, status, template):
        context.order["template"] = template_data

    context.update_template = mocker.Mock(side_effect=update_template_side_effect)
    mocked_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order,
    )

    complete_order = CompletePurchaseOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    context.update_template.assert_called_once_with(
        mpt_client_mock,
        "Completed",
        OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS,
    )
    mocked_complete_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        template=template_data,
        parameters=context.order["parameters"],
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_purchase_order_phase_invalid_phase(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.PRECONFIGURATION_MPA)
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    complete_order = CompletePurchaseOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


@pytest.mark.parametrize(
    ("order_type", "account_type", "transfer_type", "support_type", "expected_template"),
    [
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.NEW_ACCOUNT,
            "",
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS,
        ),
        (
            AccountTypesEnum.NEW_ACCOUNT,
            "",
            SupportTypesEnum.RESOLD_SUPPORT,
            ORDER_TYPE_PURCHASE,
            OrderCompletedTemplateEnum.NEW_ACCOUNT_WITHOUT_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.SPLIT_BILLING,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            OrderCompletedTemplateEnum.SPLIT_BILLING,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITH_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            SupportTypesEnum.RESOLD_SUPPORT,
            OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITHOUT_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITH_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            SupportTypesEnum.RESOLD_SUPPORT,
            OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITHOUT_PLS,
        ),
        (ORDER_TYPE_CHANGE, "", "", "", OrderCompletedTemplateEnum.CHANGE),
        (ORDER_TYPE_TERMINATION, "", "", "", OrderCompletedTemplateEnum.TERMINATION),
    ],
)
def test_completed_template_by_order(
    account_type: AccountTypesEnum,
    support_type: SupportTypesEnum,
    transfer_type: TransferTypesEnum,
    order_type: str,
    expected_template: OrderCompletedTemplateEnum,
    order_factory,
    order_parameters_factory,
):
    order_new_account = order_factory(
        order_type=order_type,
        order_parameters=order_parameters_factory(
            account_type=account_type,
            support_type=support_type,
            transfer_type=transfer_type,
        ),
    )
    step = CompleteOrderStep()
    assert step.get_template_name(InitialAWSContext(order=order_new_account)) == expected_template


def test_complete_change_order(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=""),
        order_type=ORDER_TYPE_CHANGE,
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = ChangeContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    template = {"id": "TPL-964-112", "name": OrderCompletedTemplateEnum.CHANGE}
    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=template,
    )

    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value={"id": "TPL-964-112"},
    )
    mocked_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order,
    )

    complete_order = CompleteChangeOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock,
        "PRD-1111-1111",
        MPT_ORDER_STATUS_COMPLETED,
        OrderCompletedTemplateEnum.CHANGE,
    )
    mocked_complete_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        template={"id": "TPL-964-112"},
        parameters=context.order["parameters"],
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
