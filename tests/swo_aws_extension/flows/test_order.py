import pytest

from swo_aws_extension.constants import (
    ORDER_DEFAULT_PROCESSING_TEMPLATE,
    OrderCompletedTemplateEnum,
    OrderProcessingTemplateEnum,
    OrderQueryingTemplateEnum,
)
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_COMPLETED,
    MPT_ORDER_STATUS_PROCESSING,
    MPT_ORDER_STATUS_QUERYING,
    InitialAWSContext,
    PurchaseContext,
    TerminateContext,
)


@pytest.fixture()
def order_context(order):
    return PurchaseContext.from_order_data(order)


def test_order_string_representation(mock_order):
    order_context = PurchaseContext(mock_order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation

    TerminateContext.from_order_data(mock_order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation


def test_close_account_context(order_close_account):
    context = TerminateContext.from_order_data(order_close_account)
    assert context.order == order_close_account
    assert context.terminating_subscriptions_aws_account_ids == ["1234-5678"]


def test_close_account_context_multiple(
    order_termination_close_account_multiple, order_unlink_account
):
    context = TerminateContext.from_order_data(order_termination_close_account_multiple)
    assert context.terminating_subscriptions_aws_account_ids == [
        "000000001",
        "000000002",
        "000000003",
    ]


def test_purchase_context_get_account_ids(
    mocker, order_factory, order_parameters_factory, fulfillment_parameters_factory
):
    def create_order(order_ids):
        return order_factory(
            order_parameters=order_parameters_factory(account_id=order_ids),
            fulfillment_parameters=fulfillment_parameters_factory(),
        )

    order_ids = """
    123456789
    123456788
    123456787
    123456789

    """

    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == {"123456789", "123456787", "123456788"}

    order_ids = ""
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == set()

    order_ids = " "
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == set()

    order_ids = None
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == set()

    order_ids = "123456789"
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == {"123456789"}


def test_update_template_missing_template_shows_error(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    new_template = template_factory(name=OrderProcessingTemplateEnum.NEW_ACCOUNT)
    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=new_template,
    )
    order = order_factory(template=default_template, status=MPT_ORDER_STATUS_COMPLETED)

    mock_error_logger = mocker.patch(
        "swo_aws_extension.flows.order.logger.error",
    )

    context = InitialAWSContext.from_order_data(order)
    context._update_template(mock_client, MPT_ORDER_STATUS_COMPLETED, "NonExistingTemplate")
    mock_error_logger.assert_called_once()


def test_update_processing_template_success(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    new_template = template_factory(name=OrderProcessingTemplateEnum.NEW_ACCOUNT)

    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=new_template,
    )

    order = order_factory(template=default_template)

    update_order_side_effect = update_order_side_effect_factory(order)
    mock_update_order = mocker.patch(
        "swo_aws_extension.flows.order.update_order",
        side_effect=update_order_side_effect,
    )

    mock_send_mpt_notification = mocker.patch(
        "swo_aws_extension.flows.order.send_mpt_notification",
    )

    context = InitialAWSContext.from_order_data(order)
    context.update_processing_template(mock_client, "new-template")

    assert context.template == new_template
    mock_update_order.assert_called_once_with(
        mock_client,
        "ORD-0792-5000-2253-4210",
        parameters=order["parameters"],
        template=new_template,
    )
    mock_send_mpt_notification.assert_called_once_with(mock_client, context)


def test_update_processing_template_fail(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    new_template = template_factory(name=OrderProcessingTemplateEnum.NEW_ACCOUNT)

    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=new_template,
    )

    order = order_factory(template=default_template, status=MPT_ORDER_STATUS_COMPLETED)

    update_order_side_effect = update_order_side_effect_factory(order)
    mock_update_order = mocker.patch(
        "swo_aws_extension.flows.order.update_order",
        side_effect=update_order_side_effect,
    )

    mock_send_mpt_notification = mocker.patch(
        "swo_aws_extension.flows.order.send_mpt_notification",
    )

    context = InitialAWSContext.from_order_data(order)

    with pytest.raises(RuntimeError):
        context.update_processing_template(mock_client, "new-template")

    assert context.template == default_template
    mock_update_order.assert_not_called()
    mock_send_mpt_notification.assert_not_called()


def test_switch_order_status_to_process_fail(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    order = order_factory(template=default_template, status=MPT_ORDER_STATUS_PROCESSING)

    context = InitialAWSContext.from_order_data(order)

    with pytest.raises(RuntimeError):
        context.switch_order_status_to_process(mock_client, "new-template")


def test_switch_order_status_to_query_fail(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    order = order_factory(template=default_template, status=MPT_ORDER_STATUS_QUERYING)

    context = InitialAWSContext.from_order_data(order)

    with pytest.raises(RuntimeError):
        context.switch_order_status_to_query(mock_client, "new-template")


def test_switch_order_status_to_complete_fail(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    order = order_factory(template=default_template, status=MPT_ORDER_STATUS_COMPLETED)

    context = InitialAWSContext.from_order_data(order)

    with pytest.raises(RuntimeError):
        context.switch_order_status_to_complete(mock_client, "new-template")


def test_switch_order_status_to_process_success(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    new_template = template_factory(name=OrderProcessingTemplateEnum.NEW_ACCOUNT)

    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=new_template,
    )

    order = order_factory(
        template=default_template,
        status=MPT_ORDER_STATUS_QUERYING,
    )

    update_order_side_effect = update_order_side_effect_factory(order)
    mock_process_order = mocker.patch(
        "swo_aws_extension.flows.order.process_order",
        side_effect=update_order_side_effect,
    )

    mock_send_mpt_notification = mocker.patch(
        "swo_aws_extension.flows.order.send_mpt_notification",
    )

    context = InitialAWSContext.from_order_data(order)
    context.switch_order_status_to_process(mock_client, "new-template")

    assert context.template == new_template
    mock_process_order.assert_called_once_with(
        mock_client,
        "ORD-0792-5000-2253-4210",
        parameters=order["parameters"],
        template=new_template,
    )
    mock_send_mpt_notification.assert_called_once_with(mock_client, context)


def test_switch_order_status_to_query_success(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    new_template = template_factory(name=OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS)

    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=new_template,
    )

    order = order_factory(
        template=default_template,
        status=MPT_ORDER_STATUS_PROCESSING,
    )

    update_order_side_effect = update_order_side_effect_factory(order)
    mock_query_order = mocker.patch(
        "swo_aws_extension.flows.order.query_order",
        side_effect=update_order_side_effect,
    )

    mock_send_mpt_notification = mocker.patch(
        "swo_aws_extension.flows.order.send_mpt_notification",
    )

    context = InitialAWSContext.from_order_data(order)
    context.switch_order_status_to_query(
        mock_client, OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS
    )

    mock_query_order.assert_called_once_with(
        mock_client,
        "ORD-0792-5000-2253-4210",
        parameters=order["parameters"],
        template=new_template,
    )
    mock_send_mpt_notification.assert_called_once_with(mock_client, context)


def test_switch_order_status_to_complete_success(
    mocker, order_factory, template_factory, update_order_side_effect_factory
):
    mock_client = mocker.Mock()
    default_template = template_factory(name=ORDER_DEFAULT_PROCESSING_TEMPLATE)
    new_template = template_factory(name=OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS)

    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=new_template,
    )

    order = order_factory(
        template=default_template,
        status=MPT_ORDER_STATUS_PROCESSING,
    )

    update_order_side_effect = update_order_side_effect_factory(order)
    mock_complete_order = mocker.patch(
        "swo_aws_extension.flows.order.complete_order",
        side_effect=update_order_side_effect,
    )

    mock_send_mpt_notification = mocker.patch(
        "swo_aws_extension.flows.order.send_mpt_notification",
    )

    context = InitialAWSContext.from_order_data(order)
    context.switch_order_status_to_complete(
        mock_client, OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS
    )

    mock_complete_order.assert_called_once_with(
        mock_client,
        "ORD-0792-5000-2253-4210",
        parameters=order["parameters"],
        template=new_template,
    )
    mock_send_mpt_notification.assert_called_once_with(mock_client, context)
