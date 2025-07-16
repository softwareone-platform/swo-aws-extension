from unittest import mock

import pytest

from swo_aws_extension.constants import OrderCompletedTemplateEnum, PhasesEnum
from swo_aws_extension.flows.order import (
    InitialAWSContext,
)
from swo_aws_extension.flows.steps.complete_order import CompleteOrderStep


@pytest.fixture
def context(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED)
    )
    order_context = InitialAWSContext.from_order_data(order)
    return order_context


@pytest.fixture
def client():
    return mock.Mock()


@pytest.fixture
def next_step():
    return mock.Mock()


def test_complete_order_success(
    mocker, client, context, next_step, mock_switch_order_status_to_complete
):
    step = CompleteOrderStep()
    mocker.patch("swo_aws_extension.flows.steps.complete_order.logger")
    step(client, context, next_step)
    mock_switch_order_status_to_complete.assert_called_once_with(
        client, OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS
    )
    next_step.assert_called_once_with(client, context)
