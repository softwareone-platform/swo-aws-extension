import pytest

from swo_aws_extension.airtable.models import get_master_payer_account_pool_model
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.register_transfered_mpa_airtable import (
    RegisterTransferredMPAToAirtableStep,
)


@pytest.fixture
def organization_details_response_data():
    organization_details = {
        "MasterAccountArn": "arn:aws:organizations::111111111111:"
        "account/o-exampleorgid/111111111111",
        "MasterAccountEmail": "bill@example.com",
        "MasterAccountId": "111111111111",
        "Id": "o-exampleorgid",
        "FeatureSet": "ALL",
        "Arn": "arn:aws:organizations::111111111111:organization/o-exampleorgid",
        "AvailablePolicyTypes": [{"Status": "ENABLED", "Type": "SERVICE_CONTROL_POLICY"}],
    }
    return {"Organization": organization_details}


@pytest.fixture
def mpa_pool_model_mock(base_info):
    return get_master_payer_account_pool_model(base_info)


def test_success(
    mocker,
    order_factory,
    mpa_pool_model_mock,
    agreement_factory,
    mpt_client,
    config,
    aws_client_factory,
    organization_details_response_data,
):
    order = order_factory(
        agreement=agreement_factory(
            vendor_id="123456789012",
        )
    )
    mpa_pool_model_mock.save = mocker.MagicMock()
    mpa_pool_model_mock.first = mocker.MagicMock(return_value=None)
    mocker.patch(
        "swo_aws_extension.flows.steps.register_transfered_mpa_airtable.get_master_payer_account_pool_model",
        return_value=mpa_pool_model_mock,
    )
    logger = mocker.patch("swo_aws_extension.flows.steps.register_transfered_mpa_airtable.logger")
    aws_client, aws_mock = aws_client_factory(config, "test_account_id", "test_role_name")
    aws_mock.list_account_aliases.return_value = {
        "AccountAliases": ["test_account_alias"],
    }
    aws_mock.describe_organization.return_value = organization_details_response_data
    next_step = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    step = RegisterTransferredMPAToAirtableStep()

    step(mpt_client, context, next_step)

    assert "Created MPA in Airtable" in logger.info.call_args[0][0]
    mpa_pool_model_mock.save.assert_called_once()
    next_step.assert_called_once()

    # If created MPA in Airtable, we skip to the next step
    mpa_pool_model_mock.first = mocker.MagicMock(return_value=mpa_pool_model_mock)
    logger = mocker.patch("swo_aws_extension.flows.steps.register_transfered_mpa_airtable.logger")
    step(mpt_client, context, next_step)
    assert "- Skip -" in logger.info.call_args[0][0]


def test_skip(
    mocker,
    order_factory,
    mpa_pool_model_mock,
    agreement_factory,
    mpt_client,
    config,
    aws_client_factory,
    organization_details_response_data,
):
    order = order_factory(
        agreement=agreement_factory(
            vendor_id="123456789012",
        )
    )
    mpa_pool_model_mock.save = mocker.MagicMock()
    mpa_pool_model_mock.first = mocker.MagicMock(return_value=None)
    mocker.patch(
        "swo_aws_extension.flows.steps.register_transfered_mpa_airtable.get_master_payer_account_pool_model",
        return_value=mpa_pool_model_mock,
    )
    logger = mocker.patch("swo_aws_extension.flows.steps.register_transfered_mpa_airtable.logger")
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = PurchaseContext(aws_client=aws_client, order=order, airtable_mpa=mpa_pool_model_mock)
    next_step = mocker.MagicMock()
    step = RegisterTransferredMPAToAirtableStep()

    step(mpt_client, context, next_step)

    assert "- Skip -" in logger.info.call_args[0][0]
    mpa_pool_model_mock.save.assert_not_called()
    next_step.assert_called_once()


def test_fail(
    mocker,
    order_factory,
    mpa_pool_model_mock,
    agreement_factory,
    mpt_client,
    config,
    aws_client_factory,
    organization_details_response_data,
):
    order = order_factory(
        agreement=agreement_factory(
            vendor_id="123456789012",
        )
    )
    mpa_pool_model_mock.save = mocker.MagicMock()
    mpa_pool_model_mock.first = mocker.MagicMock(return_value=None)
    mocker.patch(
        "swo_aws_extension.flows.steps.register_transfered_mpa_airtable.get_master_payer_account_pool_model",
        return_value=mpa_pool_model_mock,
    )

    context = PurchaseContext(aws_client=None, order=order, airtable_mpa=None)
    next_step = mocker.MagicMock()
    step = RegisterTransferredMPAToAirtableStep()
    with pytest.raises(AssertionError):
        step(mpt_client, context, next_step)
