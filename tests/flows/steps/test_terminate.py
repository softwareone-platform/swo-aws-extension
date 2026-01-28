import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.aws.errors import AWSError, InvalidDateInTerminateResponsibilityError
from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import FailStepError, SkipStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.terminate import TerminateResponsibilityTransferStep

JUNE_YEAR = 2025
DECEMBER_YEAR = 2026


def _get_end_of_month(year, month):
    first_day = dt.datetime(year, month, 1, 0, 0, 0, tzinfo=dt.UTC)
    return first_day - dt.timedelta(milliseconds=1)


def test_pre_step_skips_when_no_transfer_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="",
        )
    )
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=None)
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(SkipStepError) as exc_info:
        step.pre_step(context)

    assert "Responsibility transfer ID is missing" in str(exc_info.value)


def test_pre_step_proceeds_with_transfer_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    step = TerminateResponsibilityTransferStep(config)

    step.pre_step(context)  # act

    assert context.order is not None


@freeze_time("2025-06-15")
def test_process_terminates_accepted_transfer(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(JUNE_YEAR, 7)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    mock_aws_client.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123:billinggroup/test-group"
    )


@freeze_time("2025-12-15")
def test_process_success_december(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(DECEMBER_YEAR, 1)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    mock_aws_client.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123:billinggroup/test-group"
    )


@freeze_time("2025-06-15")
def test_process_skips_non_accepted_transfer(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": "Pending"}
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_not_called()
    mock_aws_client.delete_billing_group.assert_not_called()
    assert "Skipping termination as transfer status is Pending" in caplog.text


@freeze_time("2025-06-15")
def test_process_delete_billing_group_error(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_aws_client.delete_billing_group.side_effect = AWSError("Billing group deletion failed")
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_called_once()
    mock_aws_client.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123:billinggroup/test-group"
    )
    assert "Failed to delete billing group with error" in caplog.text


@freeze_time("2025-06-15")
def test_process_exception_handling(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_aws_client.terminate_responsibility_transfer.side_effect = AWSError("AWS API error")
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(UnexpectedStopError) as exc_info:
        step.process(mpt_client, context)

    assert "Terminate responsibility transfer" in exc_info.value.title
    assert "unhandled exception while terminating responsibility transfer" in exc_info.value.message


@freeze_time("2025-06-15")
def test_process_wrong_date(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_aws_client.terminate_responsibility_transfer.side_effect = (
        InvalidDateInTerminateResponsibilityError(
            "Invalid date provided for termination",
            dt.datetime.now(tz=dt.UTC),
        )
    )
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(FailStepError):
        step.process(mpt_client, context)  # act


@freeze_time("2025-06-15")
def test_post_step_logs_success(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    step = TerminateResponsibilityTransferStep(config)

    step.post_step(mpt_client, context)  # act

    assert "responsibility transfer completed successfully" in caplog.text


@freeze_time("2025-06-15")
def test_full_step_execution(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_step,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    step = TerminateResponsibilityTransferStep(config)

    step(mpt_client, context, mock_step)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_called_once()
    mock_step.assert_called_once_with(mpt_client, context)


def test_remove_billing_group_success(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
):
    billing_group_arn = "arn:aws:billingconductor::123:billinggroup/test-group"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            billing_group_arn=billing_group_arn,
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    step = TerminateResponsibilityTransferStep(config)

    step.remove_billing_group(context)  # act

    mock_aws_client.delete_billing_group.assert_called_once_with(billing_group_arn)


def test_remove_relationship_success(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    aws_client_factory,
):
    relationship_id = "rel-123456"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id=relationship_id,
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_apn_client.get_program_management_id_by_account.return_value = "pma-identifier-123"
    step = TerminateResponsibilityTransferStep(config)

    step.remove_relationship(context)  # act

    mock_apn_client.get_program_management_id_by_account.assert_called_once_with(
        context.pm_account_id
    )
    mock_apn_client.delete_pc_relationship.assert_called_once_with(
        "pma-identifier-123", relationship_id
    )


def test_remove_relationship_fail_program_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    aws_client_factory,
):
    relationship_id = "rel-123456"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id=relationship_id,
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_apn_client.get_program_management_id_by_account.side_effect = AWSError("AWS API error")
    step = TerminateResponsibilityTransferStep(config)

    step.remove_relationship(context)  # act

    mock_apn_client.get_program_management_id_by_account.assert_called_once_with(
        context.pm_account_id
    )
    mock_apn_client.delete_pc_relationship.assert_not_called()


def test_remove_relationship_fail_delete(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    aws_client_factory,
):
    relationship_id = "rel-123456"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id=relationship_id,
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    step = TerminateResponsibilityTransferStep(config)
    mock_apn_client.delete_pc_relationship.side_effect = AWSError("AWS API error")

    step.remove_relationship(context)  # act


@freeze_time("2025-06-15")
def test_terminate_relationship_transfer_success(
    config,
    mock_aws_client,
    order_factory,
    fulfillment_parameters_factory,
):
    rt_id = "rt-8lr3q6sn"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id=rt_id,
        )
    )
    context = InitialAWSContext(aws_client=mock_aws_client, order=order)
    step = TerminateResponsibilityTransferStep(config)

    step.terminate_relationship_transfer(context, rt_id)  # act

    expected_end = _get_end_of_month(JUNE_YEAR, 7)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        rt_id,
        end_timestamp=expected_end,
    )
