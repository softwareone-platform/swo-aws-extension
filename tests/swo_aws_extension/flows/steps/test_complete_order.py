from unittest import mock

import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_COMPLETED,
    InitialAWSContext,
)
from swo_aws_extension.flows.steps.complete_order import CompleteOrder


@pytest.fixture()
def context(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED)
    )
    order_context = InitialAWSContext(
        order=order,
    )
    return order_context


@pytest.fixture()
def client():
    return mock.Mock()


@pytest.fixture()
def next_step():
    return mock.Mock()


def test_complete_order_success(mocker, client, context, next_step):
    template_name = "template_123"
    step = CompleteOrder(template_name)
    mock_get_template = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default"
    )
    mock_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order"
    )
    mock_send_email = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.send_email_notification"
    )
    mocker.patch("swo_aws_extension.flows.steps.complete_order.logger")

    mock_get_template.return_value = "template"
    mock_complete_order.return_value = context.order

    step(client, context, next_step)

    mock_get_template.assert_called_once_with(
        client, context.product_id, MPT_ORDER_STATUS_COMPLETED, template_name
    )

    expected_parameters = context.order["parameters"]
    mock_complete_order.assert_called_once_with(
        client, context.order_id, "template", parameters=expected_parameters
    )
    mock_send_email.assert_called_once_with(client, context.order)
    next_step.assert_called_once_with(client, context)
