import pytest

from swo_aws_extension.flows.jobs.billing_journal.providers import BillingAWSClientProvider

MODULE = "swo_aws_extension.flows.jobs.billing_journal.providers"


@pytest.fixture
def mock_aws_client_cls(mocker):
    return mocker.patch(f"{MODULE}.AWSClient", autospec=True)


def test_does_not_create_client_until_called(config, mock_aws_client_cls):
    BillingAWSClientProvider(config, "PMA-123")  # act

    mock_aws_client_cls.assert_not_called()


def test_creates_billing_client_when_called(config, mock_aws_client_cls):
    provider = BillingAWSClientProvider(config, "PMA-123")

    client = provider()  # act

    assert client is mock_aws_client_cls.return_value
    mock_aws_client_cls.assert_called_once_with(config, "PMA-123", config.billing_role_name)


def test_reuses_the_same_client(config, mock_aws_client_cls):
    provider = BillingAWSClientProvider(config, "PMA-123")

    clients = [provider(), provider()]  # act

    assert clients[0] is clients[1]
    mock_aws_client_cls.assert_called_once()
