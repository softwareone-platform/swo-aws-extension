from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.wrap_http_error import MPTError

from swo_aws_extension.constants import OrderQueryingTemplateEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.order_utils import (
    set_order_template,
    switch_order_status_to_failed_and_notify,
    switch_order_status_to_process_and_notify,
    switch_order_status_to_query_and_notify,
)


def test_set_order_template(mocker, order_factory, fulfillment_parameters_factory):
    client = mocker.MagicMock(spec=MPTClient)
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory())
    context = PurchaseContext.from_order_data(order)
    template = {"name": "MyTemplate"}
    get_template_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        return_value=template,
    )

    result = set_order_template(client, context, "Querying", "MyTemplate")

    get_template_mock.assert_called_once()
    assert context.template == template
    assert result == template


def test_switch_order_to_query_and_notify(
    mocker, order_factory, fulfillment_parameters_factory, template_factory
):
    client = mocker.MagicMock(spec=MPTClient)
    default_template = template_factory(name=OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID.value)
    new_template = template_factory(
        name=OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS.value
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(), template=default_template
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        return_value=new_template,
    )
    query_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.query_order",
        return_value=order,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    switch_order_status_to_query_and_notify(client, context, "TemplateName")  # act

    query_order_mock.assert_called_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )
    notification_mock.assert_called_once()


def test_switch_order_to_query_and_notify_error(
    mocker, order_factory, fulfillment_parameters_factory, template_factory
):
    client = mocker.MagicMock(spec=MPTClient)
    default_template = template_factory(name=OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID.value)
    new_template = template_factory(
        name=OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS.value
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(), template=default_template
    )
    mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        return_value=new_template,
    )
    order["error"] = {"id": "SomeError", "message": "An error occurred"}
    context = PurchaseContext.from_order_data(order)
    query_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.query_order",
        return_value=context.order,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    switch_order_status_to_query_and_notify(client, context, "TemplateName")  # act

    query_order_mock.assert_called_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
        error=context.order["error"],
    )
    notification_mock.assert_called_once()


def test_switch_order_to_failed_and_notify(mocker, order_factory, fulfillment_parameters_factory):
    client = mocker.MagicMock(spec=MPTClient)
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory())
    context = PurchaseContext.from_order_data(order)
    fail_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.fail_order",
        return_value=order,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    switch_order_status_to_failed_and_notify(client, context, "Failure reason")  # act

    fail_order_mock.assert_called_with(
        client,
        context.order_id,
        "Failure reason",
        parameters=context.order["parameters"],
    )
    notification_mock.assert_called_once()


def test_switch_order_to_process_and_notify(
    mocker, order_factory, fulfillment_parameters_factory, template_factory, mpt_client
):
    default_template = template_factory(name="Default")
    new_template = template_factory(name="Processing")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(), template=default_template
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        return_value=new_template,
    )
    process_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.process_order",
        return_value=order,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    switch_order_status_to_process_and_notify(mpt_client, context, "TemplateName")  # act

    process_order_mock.assert_called_once_with(
        mpt_client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )
    notification_mock.assert_called_once()


def test_switch_order_to_process_and_notify_error(
    mocker, order_factory, fulfillment_parameters_factory, template_factory, mpt_client
):
    default_template = template_factory(name="Default")
    new_template = template_factory(name="Processing")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(), template=default_template
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        return_value=new_template,
    )
    mocker.patch(
        "swo_aws_extension.flows.order_utils.process_order",
        side_effect=MPTError("error"),
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    switch_order_status_to_process_and_notify(mpt_client, context, "TemplateName")  # act

    notification_mock.assert_not_called()
