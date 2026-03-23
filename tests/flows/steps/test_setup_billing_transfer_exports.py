import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.setup_billing_transfer_exports import (
    SetupBillingTransferExports,
    extract_billing_view_id,
)
from swo_aws_extension.parameters import get_mpa_account_id, get_phase


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.Mock(spec=AWSClient)


@pytest.fixture
def purchase_context(order_factory, fulfillment_parameters_factory, mock_aws_client):
    def factory(
        phase=PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS.value,
        authorization_external_id="123456789012",
    ):
        order = order_factory(
            authorization_external_id=authorization_external_id,
            fulfillment_parameters=fulfillment_parameters_factory(phase=phase),
        )
        ctx = PurchaseContext.from_order_data(order)
        ctx.aws_client = mock_aws_client
        return ctx

    return factory


@pytest.mark.parametrize(
    ("billing_view_arn", "expected_id"),
    [
        (
            "arn:aws:billing::123456789012:billingview/billing-transfer-abc123",
            "abc123",
        ),
        (
            "arn:aws:billing::123456789012:billingview/billing-transfer-",
            "",
        ),
        (
            "arn:aws:billing::123456789012:billingview/custom-view",
            "custom-view",
        ),
        (
            "no-slash-arn",
            "no-slash-arn",
        ),
    ],
)
def test_extract_billing_view_id(billing_view_arn, expected_id):
    result = extract_billing_view_id(billing_view_arn)

    assert result == expected_id


def test_pre_step_skips_wrong_phase(purchase_context, config):
    context = purchase_context(phase=PhasesEnum.COMPLETED.value)
    step = SetupBillingTransferExports(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_pre_step_passes_correct_phase(purchase_context, config):
    context = purchase_context()
    step = SetupBillingTransferExports(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_creates_exports_for_new_views(
    purchase_context, mock_aws_client, mpt_client, config
):
    billing_view_arn = "arn:aws:billing::123456789012:billingview/billing-transfer-abc123"
    context = purchase_context(authorization_external_id="651706759263")
    mpa_id = get_mpa_account_id(context.order)
    pma_id = context.pm_account_id
    expected_bucket = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pma_id)
    expected_prefix = S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=mpa_id)
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {
            "billingViewArn": billing_view_arn,
            "sourceAccountId": mpa_id,
        }
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()
    mock_aws_client.create_billing_export.return_value = (
        "arn:aws:bcm-data-exports::123:export/exp-001"
    )
    step = SetupBillingTransferExports(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.create_billing_export.assert_called_once_with(
        billing_view_arn=billing_view_arn,
        export_name=f"{mpa_id}-abc123",
        s3_bucket=expected_bucket,
        s3_prefix=f"{expected_prefix}/billing-transfer-abc123",
    )


def test_process_skips_already_exported_views(
    purchase_context, mock_aws_client, mpt_client, config
):
    billing_view_arn = "arn:aws:billing::123456789012:billingview/billing-transfer-abc123"
    context = purchase_context()
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"billingViewArn": billing_view_arn, "sourceAccountId": "123456789012"}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = {billing_view_arn}
    step = SetupBillingTransferExports(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.create_billing_export.assert_not_called()


def test_process_skips_views_without_arn(
    purchase_context, mock_aws_client, mpt_client, config, caplog
):
    context = purchase_context()
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"sourceAccountId": "123456789012"}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()
    step = SetupBillingTransferExports(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.create_billing_export.assert_not_called()
    assert "arn or billingViewArn" in caplog.text


def test_process_handles_empty_views(purchase_context, mock_aws_client, mpt_client, config):
    context = purchase_context()
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    mock_aws_client.list_existing_billing_exports.return_value = set()
    step = SetupBillingTransferExports(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.create_billing_export.assert_not_called()


def test_process_raises_on_aws_error_listing_views(
    purchase_context, mock_aws_client, mpt_client, config
):
    context = purchase_context()
    mock_aws_client.get_current_billing_view_by_account_id.side_effect = AWSError("API error")
    step = SetupBillingTransferExports(config)

    with pytest.raises(UnexpectedStopError):
        step.process(mpt_client, context)


def test_process_raises_on_aws_error_listing_exports(
    purchase_context, mock_aws_client, mpt_client, config
):
    context = purchase_context()
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    mock_aws_client.list_existing_billing_exports.side_effect = AWSError("API error")
    step = SetupBillingTransferExports(config)

    with pytest.raises(UnexpectedStopError):
        step.process(mpt_client, context)


def test_process_logs_warning_on_failed_export(
    purchase_context, mock_aws_client, mpt_client, config, caplog
):
    billing_view_arn = "arn:aws:billing::123456789012:billingview/billing-transfer-abc123"
    context = purchase_context()
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"billingViewArn": billing_view_arn, "sourceAccountId": "123456789012"}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()
    mock_aws_client.create_billing_export.side_effect = AWSError("Export creation failed")
    step = SetupBillingTransferExports(config)

    step.process(mpt_client, context)  # act

    assert "Failed to create billing export" in caplog.text


def test_post_step_advances_phase_to_completed(
    mocker, purchase_context, mpt_client, config, order_factory, fulfillment_parameters_factory
):
    context = purchase_context()
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value)
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_billing_transfer_exports.update_order",
        return_value=updated_order,
    )
    step = SetupBillingTransferExports(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.COMPLETED.value


def test_post_step_calls_update_order(
    mocker, purchase_context, mpt_client, config, order_factory, fulfillment_parameters_factory
):
    context = purchase_context()
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value)
    )
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.setup_billing_transfer_exports.update_order",
        return_value=updated_order,
    )
    step = SetupBillingTransferExports(config)

    step.post_step(mpt_client, context)  # act

    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][0] == mpt_client
    assert call_args[0][1] == context.order_id
