from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import SetupAgreementIdInAccountTagsStep


def test_setup_agreement_id_in_account_tags_success(
    mocker,
    aws_client_factory,
    config,
    aws_accounts_factory,
    order_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CREATE_SUBSCRIPTIONS)
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_accounts.return_value = aws_accounts_factory()
    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    setup_account_tags = SetupAgreementIdInAccountTagsStep()
    setup_account_tags(client=mpt_client_mock, context=context, next_step=next_step_mock)

    mock_client.list_accounts.assert_called_once()
    assert mock_client.tag_resource.call_count == 1

    mock_client.tag_resource.assert_called_once_with(
        ResourceId="123456789012",
        Tags=[{"Key": "agreement_id", "Value": "AGR-2119-4550-8674-5962"}],
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_agreement_id_in_account_tags_no_active_accounts(
    mocker,
    aws_client_factory,
    config,
    order_factory,
    aws_accounts_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CREATE_SUBSCRIPTIONS)
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_accounts.return_value = aws_accounts_factory(status="SUSPENDED")
    mock_client.add_tags_for_resource = mocker.Mock()

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    setup_account_tags = SetupAgreementIdInAccountTagsStep()
    setup_account_tags(client=mpt_client_mock, context=context, next_step=next_step_mock)

    mock_client.list_accounts.assert_called_once()
    mock_client.add_tags_for_resource.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_agreement_id_skip_phase(
    mocker,
    aws_client_factory,
    config,
    aws_accounts_factory,
    order_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED)
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_accounts.return_value = aws_accounts_factory()
    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    setup_account_tags = SetupAgreementIdInAccountTagsStep()
    setup_account_tags(client=mpt_client_mock, context=context, next_step=next_step_mock)

    mock_client.list_accounts.assert_not_called()
    mock_client.tag_resource.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
