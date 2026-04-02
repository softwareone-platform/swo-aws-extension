from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.wrap_http_error import MPTError

from swo_aws_extension.constants import OrderCompletedTemplate, OrderQueryingTemplateEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.order_utils import (
    set_order_template,
    strip_whitespace_from_mpa_account,
    switch_order_status_to_complete,
    switch_order_status_to_failed,
    switch_order_status_to_process,
    switch_order_status_to_query,
    update_processing_template_and_notify,
)
from swo_aws_extension.parameters import get_mpa_account_id


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
    assert result == context.order


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

    switch_order_status_to_query(client, context, "TemplateName")  # act

    query_order_mock.assert_called_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )


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

    switch_order_status_to_query(client, context, "TemplateName")  # act

    query_order_mock.assert_called_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
        error=context.order["error"],
    )


def test_switch_order_to_failed(mocker, order_factory, fulfillment_parameters_factory):
    client = mocker.MagicMock(spec=MPTClient)
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory())
    context = PurchaseContext.from_order_data(order)
    fail_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.fail_order",
        return_value=order,
        autospec=True,
    )

    switch_order_status_to_failed(client, context, "Failure reason")  # act

    fail_order_mock.assert_called_with(
        client,
        context.order_id,
        "Failure reason",
        parameters=context.order["parameters"],
    )


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

    switch_order_status_to_process(mpt_client, context, "TemplateName")  # act

    process_order_mock.assert_called_once_with(
        mpt_client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )


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

    switch_order_status_to_process(mpt_client, context, "TemplateName")  # act

    notification_mock.assert_not_called()


def test_switch_order_status_to_complete(
    mocker, order_factory, order_parameters_factory, template_factory
):
    client = mocker.MagicMock(spec=MPTClient)
    default_template = template_factory(name=OrderCompletedTemplate.TERMINATION.value)
    new_template = template_factory(name=OrderCompletedTemplate.TERMINATION.value)
    mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        return_value=new_template,
    )
    order = order_factory(template=default_template)
    context = PurchaseContext.from_order_data(order)
    complete_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.complete_order",
        return_value=order,
    )

    switch_order_status_to_complete(client, context, "TemplateName")  # act

    complete_order_mock.assert_called_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )


def test_update_processing_template_and_notify(
    mocker, order_factory, fulfillment_parameters_factory, template_factory
):
    client = mocker.MagicMock(spec=MPTClient)
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
    update_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.update_order",
        return_value=order,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    update_processing_template_and_notify(client, context, "TemplateName")  # act

    update_order_mock.assert_called_once_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )
    notification_mock.assert_called_once()


def test_update_processing_template_no_notify(
    mocker, order_factory, fulfillment_parameters_factory, template_factory
):
    client = mocker.MagicMock(spec=MPTClient)
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
    update_order_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.update_order",
        return_value=order,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.order_utils.MPTNotificationManager",
    )

    update_processing_template_and_notify(client, context, "TemplateName", notify=False)  # act

    update_order_mock.assert_called_once_with(
        client,
        context.order_id,
        parameters=context.order["parameters"],
        template=new_template,
    )
    notification_mock.assert_not_called()


def test_strip_whitespace_from_mpa_account(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="  651706759263  "),
    )

    result = strip_whitespace_from_mpa_account(order)

    assert get_mpa_account_id(result) == "651706759263"


def test_strip_whitespace_from_mpa_account_without_value(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id=""),
    )

    result = strip_whitespace_from_mpa_account(order)

    assert not get_mpa_account_id(result)
