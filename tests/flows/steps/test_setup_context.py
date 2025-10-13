from unittest import mock

import pytest
from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE
from mpt_extension_sdk.mpt_http.base import MPTClient
from requests import Response

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import HTTP_STATUS_OK, PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import ChangeContext, PurchaseContext
from swo_aws_extension.flows.steps.setup_context import (
    SetupChangeContext,
    SetupContext,
    SetupContextPurchaseTransferWithOrgStep,
    SetupContextPurchaseTransferWithoutOrgStep,
    SetupPurchaseContext,
)
from swo_aws_extension.parameters import get_phase
from swo_aws_extension.swo_ccp.client import CCPClient


def test_setup_context_get_mpa_credentials(
    mocker,
    monkeypatch,
    order_factory,
    config,
    requests_mocker,
    agreement_factory,
    mock_mpt_key_vault_name,
):
    monkeypatch.setenv("MPT_KEY_VAULT_NAME", mock_mpt_key_vault_name)
    mocker.patch(
        "swo_aws_extension.swo_ccp.client.CCPClient.get_secret_from_key_vault",
        return_value="client_secret",
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value="client_secret",
    )
    role_name = "test_role"
    order = order_factory(agreement=agreement_factory(vendor_id="123456789012"))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=HTTP_STATUS_OK
    )
    mock_boto3_client = mocker.patch("boto3.client")
    mock_client = mock_boto3_client.return_value
    mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
    next_step_mock = mocker.Mock()
    context = PurchaseContext.from_order_data(order)
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))
    setup_context = SetupContext(config, role_name)

    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 1
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_context_without_acc_id_exception(
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
            account_request_id="account_request_id"
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    context = PurchaseContext.from_order_data(order)
    setup_context = SetupContext(config, role_name)

    with pytest.raises(ValueError):
        setup_context(mpt_client_mock, context, next_step_mock)


def test_setup_purchase_context_get_credentials(
    mocker, order_factory, config, requests_mocker, agreement_factory, mpa_pool_factory
):
    role_name = "test_role"
    order = order_factory(agreement=agreement_factory(vendor_id="123456789012"))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=HTTP_STATUS_OK
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value="client_secret",
    )
    mock_boto3_client = mocker.patch("boto3.client")
    mock_client = mock_boto3_client.return_value
    mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
    next_step_mock = mocker.Mock()
    context = PurchaseContext.from_order_data(order)
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    setup_context = SetupPurchaseContext(config, role_name)

    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 1
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_context_get_account_create_status(
    settings,
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
            account_request_id="account_request_id"
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    mocker.patch(
        "swo_aws_extension.swo_ccp.client.CCPClient.get_secret_from_key_vault",
        return_value="client_secret",
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value="client_secret",
    )
    next_step_mock = mocker.Mock()
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.describe_create_account_status.return_value = create_account_status()
    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    setup_context = SetupPurchaseContext(config, role_name)

    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    mock_client.describe_create_account_status.assert_called_once_with(
        CreateAccountRequestId="account_request_id"
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_transfer_without_organization(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    agreement_factory,
    mpa_pool_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=""),
        agreement=agreement_factory(vendor_id="123456789012"),
    )

    def dummy_update_order(_client, _id, parameters):  # noqa: WPS110
        order["parameters"] = parameters
        return order

    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_order",
        side_effect=dummy_update_order,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    setup_aws_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.SetupContextPurchaseTransferWithoutOrgStep.setup_aws"
    )
    context = PurchaseContext.from_order_data(order)
    next_step = mocker.MagicMock()
    step = SetupContextPurchaseTransferWithoutOrgStep(config, "role_name")

    step(mocker.MagicMock(), context, next_step)

    next_step.assert_called_once()
    assert get_phase(context.order) == PhasesEnum.ASSIGN_MPA
    setup_aws_mock.assert_called_once()


def test_setup_change_context(
    mocker, order_factory, config, requests_mocker, agreement_factory, mpa_pool_factory
):
    role_name = "test_role"
    order = order_factory(agreement=agreement_factory(vendor_id="123456789012"))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=HTTP_STATUS_OK
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value="client_secret",
    )
    mock_boto3_client = mocker.patch("boto3.client")
    mock_client = mock_boto3_client.return_value
    mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
    next_step_mock = mocker.Mock()
    context = ChangeContext.from_order_data(order)
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    setup_context = SetupChangeContext(config, role_name)

    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 1
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_change_context_set_account_status(
    mocker,
    order_factory,
    config,
    requests_mocker,
    agreement_factory,
    mpa_pool_factory,
    aws_client_factory,
    create_account_status,
    fulfillment_parameters_factory,
):
    role_name = "test_role"
    order = order_factory(
        agreement=agreement_factory(vendor_id="123456789012"),
        fulfillment_parameters=fulfillment_parameters_factory(account_request_id="123456789012"),
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    credentials = {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }
    requests_mocker.post(
        config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=HTTP_STATUS_OK
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value="client_secret",
    )
    next_step_mock = mocker.Mock()
    context = ChangeContext.from_order_data(order)
    mocker.patch("swo_aws_extension.aws.client.AWSClient", return_value=mock.Mock(spec=AWSClient))
    _, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.describe_create_account_status.return_value = create_account_status()
    mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )

    setup_context = SetupChangeContext(config, role_name)

    setup_context(mpt_client_mock, context, next_step_mock)

    assert isinstance(context.aws_client, AWSClient)
    assert mock_client.assume_role_with_web_identity.call_count == 2
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    assert context.account_creation_status is not None


def test_transfer_with_org_step(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="111111111111",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )
    template_response = Response()
    template_response._content = b'{"data": ["template"]}'  # noqa: SLF001
    template_response.status_code = HTTP_STATUS_OK
    mpt_client_mock.get = mocker.Mock(return_value=template_response)
    step = SetupContextPurchaseTransferWithOrgStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)

    step(mpt_client_mock, context, next_step_mock)

    mpt_client_mock.put.assert_called_once()  # Setting up phase
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_transfer_with_org_step_with_mpa(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
    mpa_pool_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="",
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    template_response = Response()
    template_response._content = b'{"data": ["template"]}'  # noqa: SLF001
    template_response.status_code = HTTP_STATUS_OK
    mpt_client_mock.get = mocker.Mock(return_value=template_response)

    setup_aws_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context."
        "SetupContextPurchaseTransferWithOrgStep.setup_aws"
    )
    step = SetupContextPurchaseTransferWithOrgStep(config, "role_name")
    context = PurchaseContext.from_order_data(order)

    step(mpt_client_mock, context, next_step_mock)

    mpt_client_mock.put.assert_called_once()  # Setting up phase
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    setup_aws_mock.assert_called_with(context)


def test_setup_querying(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mock_switch_order_status_to_query,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value,
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )
    step = SetupContextPurchaseTransferWithOrgStep(config, "role_name")
    context = PurchaseContext.from_order_data(order)

    step(mpt_client_mock, context, next_step_mock)

    mock_switch_order_status_to_query.assert_called_once()
    next_step_mock.assert_not_called()


def test_skip_purchase(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value,
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
        ),
    )

    def return_order(client, order):
        return order

    get_phase_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_phase",
        side_effect=return_order,
    )
    step = SetupContextPurchaseTransferWithOrgStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)

    step(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once()
    get_phase_mock.assert_not_called()  # first call on processing the step


def test_skip_change(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        order_type=ORDER_TYPE_CHANGE,
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value,
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
        ),
    )
    get_phase_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_phase",
        side_effect=lambda _, order: order,
    )
    step = SetupContextPurchaseTransferWithOrgStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)

    step(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once()
    get_phase_mock.assert_not_called()  # first call on processing the step
