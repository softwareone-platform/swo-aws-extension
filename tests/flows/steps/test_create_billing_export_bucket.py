import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError, S3BucketAlreadyOwnedError
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
    S3_BILLING_EXPORT_REGION,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.create_billing_export_bucket import (
    CreateBillingExportBucket,
)
from swo_aws_extension.flows.steps.errors import (
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
)


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.Mock(spec=AWSClient)


@pytest.fixture
def purchase_context(order_factory, fulfillment_parameters_factory, mock_aws_client):
    def factory(
        phase=PhasesEnum.COMPLETED.value,
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


def test_pre_step_skips_wrong_phase(purchase_context, config):
    context = purchase_context(phase=PhasesEnum.CREATE_SUBSCRIPTION.value)
    step = CreateBillingExportBucket(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_pre_step_passes_when_completed(purchase_context, config):
    context = purchase_context()
    step = CreateBillingExportBucket(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_creates_bucket_with_pma_name(
    purchase_context,
    mock_aws_client,
    mpt_client,
    config,
):
    context = purchase_context(authorization_external_id="651706759263")
    mpa_id = get_mpa_account_id(context.order)
    pma_id = context.pm_account_id
    step = CreateBillingExportBucket(config)
    expected_bucket = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pma_id)
    expected_prefix = S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=mpa_id)

    step.process(mpt_client, context)  # act

    mock_aws_client.create_s3_bucket.assert_called_once_with(
        expected_bucket, S3_BILLING_EXPORT_REGION
    )
    assert expected_bucket == f"mpt-billing-{pma_id}"
    assert expected_prefix == f"cur-{mpa_id}"


def test_process_raises_unexpected_stop_on_aws_error(
    purchase_context, mock_aws_client, mpt_client, config
):
    context = purchase_context()
    mock_aws_client.create_s3_bucket.side_effect = AWSError("Access Denied")
    step = CreateBillingExportBucket(config)

    with pytest.raises(UnexpectedStopError):
        step.process(mpt_client, context)


def test_process_skips_when_bucket_already_exists(
    purchase_context, mock_aws_client, mpt_client, config
):
    context = purchase_context()
    mock_aws_client.create_s3_bucket.side_effect = S3BucketAlreadyOwnedError("already owned")
    step = CreateBillingExportBucket(config)

    step.process(mpt_client, context)


def test_post_step_advances_phase_to_setup_billing_exports(
    mocker, purchase_context, mpt_client, config, order_factory, fulfillment_parameters_factory
):
    context = purchase_context()
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS.value
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.create_billing_export_bucket.update_order",
        return_value=updated_order,
    )
    step = CreateBillingExportBucket(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS.value


def test_post_step_calls_update_order(
    mocker, purchase_context, mpt_client, config, order_factory, fulfillment_parameters_factory
):
    context = purchase_context()
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS.value
        )
    )
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.create_billing_export_bucket.update_order",
        return_value=updated_order,
    )
    step = CreateBillingExportBucket(config)

    step.post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
