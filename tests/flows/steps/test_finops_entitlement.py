from http import HTTPStatus

import pytest

from swo_aws_extension.airtable.models import FinOpsRecord
from swo_aws_extension.constants import FinOpsStatusEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.finops_entitlement import TerminateFinOpsEntitlementStep
from swo_aws_extension.swo.finops.errors import FinOpsHttpError


@pytest.fixture
def mock_finops_table(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.finops_entitlement.FinOpsEntitlementsTable")


@pytest.fixture
def mock_ffc_client(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.finops_entitlement.get_ffc_client")


@pytest.fixture
def finops_record():
    return FinOpsRecord(
        record_id="rec123",
        account_id="123456789012",
        buyer_id="BUY-123",
        agreement_id="AGR-123",
        entitlement_id="ent-123",
        status=FinOpsStatusEnum.ACTIVE.value,
        last_usage_date="2025-06-01",
    )


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
    step = TerminateFinOpsEntitlementStep(config)

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
    step = TerminateFinOpsEntitlementStep(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_with_no_entitlements(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_finops_table,
    mock_ffc_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = []
    step = TerminateFinOpsEntitlementStep(config)

    step.process(mpt_client, context)  # act

    mock_ffc_client.return_value.delete_entitlement.assert_not_called()
    mock_ffc_client.return_value.terminate_entitlement.assert_not_called()
    assert "Managing FinOps entitlement termination" in caplog.text


def test_process_deletes_new_entitlement(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_finops_table,
    mock_ffc_client,
    finops_record,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = [finops_record]
    mock_ffc_client.return_value.get_entitlement_by_datasource.return_value = {
        "id": "ent-123",
        "status": "new",
    }
    step = TerminateFinOpsEntitlementStep(config)

    step.process(mpt_client, context)  # act

    mock_ffc_client.return_value.delete_entitlement.assert_called_once_with("ent-123")
    mock_finops_table.return_value.update_status_and_usage_date.assert_called_once()
    assert "Deleted FinOps entitlement" in caplog.text


def test_process_terminates_active_entitlement(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_finops_table,
    mock_ffc_client,
    finops_record,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = [finops_record]
    mock_ffc_client.return_value.get_entitlement_by_datasource.return_value = {
        "id": "ent-123",
        "status": "active",
    }
    step = TerminateFinOpsEntitlementStep(config)

    step.process(mpt_client, context)  # act

    mock_ffc_client.return_value.terminate_entitlement.assert_called_once_with("ent-123")
    mock_finops_table.return_value.update_status_and_usage_date.assert_called_once()
    assert "Terminated FinOps entitlement" in caplog.text


def test_process_handles_missing_entitlement(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_finops_table,
    mock_ffc_client,
    finops_record,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = [finops_record]
    mock_ffc_client.return_value.get_entitlement_by_datasource.return_value = None
    step = TerminateFinOpsEntitlementStep(config)

    step.process(mpt_client, context)  # act

    mock_ffc_client.return_value.delete_entitlement.assert_not_called()
    mock_ffc_client.return_value.terminate_entitlement.assert_not_called()
    mock_finops_table.return_value.update_status_and_usage_date.assert_called_once()
    assert "not found in FinOps" in caplog.text


def test_process_skips_unknown_status(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_finops_table,
    mock_ffc_client,
    finops_record,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = [finops_record]
    mock_ffc_client.return_value.get_entitlement_by_datasource.return_value = {
        "id": "ent-123",
        "status": "unknown",
    }
    step = TerminateFinOpsEntitlementStep(config)

    step.process(mpt_client, context)  # act

    mock_ffc_client.return_value.delete_entitlement.assert_not_called()
    mock_ffc_client.return_value.terminate_entitlement.assert_not_called()
    mock_finops_table.return_value.update_status_and_usage_date.assert_called_once()


def test_process_raises_error_on_finops(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_finops_table,
    mock_ffc_client,
    finops_record,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = [finops_record]
    mock_ffc_client.return_value.get_entitlement_by_datasource.side_effect = FinOpsHttpError(
        HTTPStatus.INTERNAL_SERVER_ERROR, "FinOps API error"
    )
    step = TerminateFinOpsEntitlementStep(config)

    with pytest.raises(UnexpectedStopError) as exc_info:
        step.process(mpt_client, context)

    assert "FinOps Entitlement Termination" in exc_info.value.title
    assert "123456789012" in exc_info.value.message


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
    step = TerminateFinOpsEntitlementStep(config)

    step.post_step(mpt_client, context)  # act

    assert "Completed FinOps entitlement termination step" in caplog.text


def test_full_step_execution(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    mock_step,
    mock_finops_table,
    mock_ffc_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_finops_table.return_value.get_by_agreement_id.return_value = []
    step = TerminateFinOpsEntitlementStep(config)

    step(mpt_client, context, mock_step)  # act

    mock_step.assert_called_once_with(mpt_client, context)
