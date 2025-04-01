from unittest import mock

import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.setup_context import (
    SetupContext,
    SetupPurchaseContext,
)


def test_setup_context_get_mpa_credentials(mocker, order_factory, config, requests_mocker):
    role_name = "test_role"
    order = order_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=200
    )

    mock_boto3_client = mocker.patch("boto3.client")
    mock_client = mock_boto3_client.return_value

    mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
    next_step_mock = mocker.Mock()

    context = PurchaseContext(order=order)

    mocker.patch("swo_aws_extension.parameters.get_mpa_account_id", return_value="123456789012")
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))

    setup_context = SetupContext(config, role_name)
    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 1
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_context_without_account_id_raise_exception(
    mocker,
    order_factory,
    config,
    requests_mocker,
    fulfillment_parameters_factory,
    aws_client_factory,
    create_account_status,
):
    role_name = "test_role"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            account_request_id="account_request_id", mpa_account_id=""
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)

    next_step_mock = mocker.Mock()
    context = PurchaseContext(order=order)
    setup_context = SetupContext(config, role_name)
    with pytest.raises(ValueError):
        setup_context(mpt_client_mock, context, next_step_mock)


def test_setup_purchase_context_get_mpa_credentials(mocker, order_factory, config, requests_mocker):
    role_name = "test_role"
    order = order_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=200
    )

    mock_boto3_client = mocker.patch("boto3.client")
    mock_client = mock_boto3_client.return_value

    mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
    next_step_mock = mocker.Mock()

    context = PurchaseContext(order=order)

    mocker.patch("swo_aws_extension.parameters.get_mpa_account_id", return_value="123456789012")
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))

    setup_context = SetupPurchaseContext(config, role_name)
    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 1
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_context_get_account_creation_status(
    mocker,
    order_factory,
    config,
    requests_mocker,
    fulfillment_parameters_factory,
    aws_client_factory,
    create_account_status,
):
    role_name = "test_role"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            account_request_id="account_request_id", mpa_account_id=""
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)

    next_step_mock = mocker.Mock()
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.describe_create_account_status.return_value = create_account_status()

    context = PurchaseContext(order=order)
    context.aws_client = aws_client

    setup_context = SetupPurchaseContext(config, role_name)
    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    mock_client.describe_create_account_status.assert_called_once_with(
        CreateAccountRequestId="account_request_id"
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
