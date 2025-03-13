from unittest.mock import Mock, create_autospec

import pytest
from swo.mpt.client import MPTClient

from swo_aws_extension.flows.order import CloseAccountContext
from swo_aws_extension.flows.steps.close_aws_account import CloseAWSAccountStep


@pytest.fixture()
def aws_client():
    return Mock()


@pytest.fixture()
def close_aws_account():
    return CloseAWSAccountStep()


@pytest.fixture()
def context(aws_client, order_factory, order_parameters_factory):
    close_context = create_autospec(CloseAccountContext, instance=True)
    close_context.order = order_factory(
        order_parameters=order_parameters_factory(
            account_id="close_account_id"
        )
    )
    close_context.aws_client = aws_client
    return close_context


@pytest.fixture()
def next_step():
    return Mock()


def test_close_aws_account_success(mocker, close_aws_account, aws_client, context, next_step):
    client = Mock(spec=MPTClient)
    close_aws_account(client, context, next_step)
    aws_client.close_account.assert_called_once_with("close_account_id")
    next_step.assert_called_once_with(client, context)
