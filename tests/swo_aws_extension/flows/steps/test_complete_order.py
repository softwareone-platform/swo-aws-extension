from unittest import mock

import pytest

from swo_aws_extension.constants import OrderCompletedTemplateEnum, PhasesEnum
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_COMPLETED,
    InitialAWSContext,
)
from swo_aws_extension.flows.steps.complete_order import CompleteOrderStep


@pytest.fixture()
def context(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED)
    )
    order_context = InitialAWSContext.from_order_data(order)
    return order_context


@pytest.fixture()
def client():
    return mock.Mock()


@pytest.fixture()
def next_step():
    return mock.Mock()


def test_complete_order_success(mocker, client, context, next_step):
    step = CompleteOrderStep()

    mock_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order"
    )
    mock_send_email = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.send_email_notification"
    )
    mocker.patch("swo_aws_extension.flows.steps.complete_order.logger")

    template_data = {"id": "TPL-964-112", "name": OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS}
    mock_get_template = mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=template_data,
    )
    mock_complete_order.return_value = context.order

    step(client, context, next_step)

    mock_get_template.assert_called_once_with(
        client,
        context.product_id,
        MPT_ORDER_STATUS_COMPLETED,
        OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS,
    )

    expected_parameters = context.order["parameters"]
    mock_complete_order.assert_called_once_with(
        client, context.order_id, template=template_data, parameters=expected_parameters
    )
    mock_send_email.assert_called_once_with(client, context.order, context.buyer)
    next_step.assert_called_once_with(client, context)
