from unittest.mock import Mock

import pytest
from swo.mpt.client import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import TerminateContext
from swo_aws_extension.flows.steps import TerminateAWSAccount


@pytest.fixture()
def aws_client():
    return Mock()


@pytest.fixture()
def context(
    aws_client,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    subscriptions_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(account_id="close_account_id"),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.PRECONFIGURATION_MPA
        ),
        subscriptions=subscriptions_factory(
            vendor_id="close_account_id", status="Terminating"
        ),
    )
    context = TerminateContext.from_order(order)
    context.aws_client = aws_client
    return context


@pytest.fixture()
def next_step():
    return Mock()


def test_close_aws_account_success(
    aws_client, context, next_step, data_aws_account_factory
):
    client = Mock(spec=MPTClient)

    aws_client.list_accounts.return_value = [
        data_aws_account_factory(id="close_account_id", status="ACTIVE")
    ]
    terminate_account_step = TerminateAWSAccount()
    terminate_account_step(client, context, next_step)
    aws_client.close_account.assert_called_once_with("close_account_id")
    next_step.assert_called_once_with(client, context)
