import pytest
from mpt_extension_sdk.flows.pipeline import Step

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.order import InitialAWSContext


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.Mock(spec=AWSClient)


@pytest.fixture
def mock_aws_apn_client(mocker):
    return mocker.Mock(spec=AWSClient)


@pytest.fixture
def context_with_agreement(agreement_factory, order_factory, config, mock_aws_client):
    agreement = agreement_factory()
    return InitialAWSContext(aws_client=mock_aws_client, order=order_factory(), agreement=agreement)


@pytest.fixture
def context_without_agreement(order_factory, config, mock_aws_client):
    return InitialAWSContext(aws_client=mock_aws_client, order=order_factory(), agreement=None)


@pytest.fixture
def context_without_transfer_id(agreement_factory, order_factory, config, mock_aws_client):
    agreement = agreement_factory(fulfillment_parameters=[])
    return InitialAWSContext(aws_client=mock_aws_client, order=order_factory(), agreement=agreement)


@pytest.fixture
def mock_step(mocker):
    return mocker.MagicMock(spec=Step)


@pytest.fixture
def mock_switch_order_status_to_complete(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.order.InitialAWSContext.switch_order_status_to_complete"
    )
