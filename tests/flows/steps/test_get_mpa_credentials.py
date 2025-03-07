from unittest import mock

from swo.mpt.client import MPTClient

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.flows.steps.get_mpa_credentials import GetMPACredentials


def test_get_mpa_credentials_success(mocker, order_factory, config, requests_mocker):
    role_name = "test_role"
    order = order_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url,
        json={"access_token": "test_access_token"},
        status=200)

    mock_boto3_client = mocker.patch("boto3.client")
    mock_client = mock_boto3_client.return_value

    mock_client.assume_role_with_web_identity.return_value = {
        "Credentials": credentials
    }
    next_step_mock = mocker.Mock()

    context = OrderContext.from_order(order)

    mocker.patch("swo_aws_extension.parameters.get_mpa_account_id", return_value="123456789012")
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))

    get_mpa_credentials = GetMPACredentials(config, role_name)
    get_mpa_credentials(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 1
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
