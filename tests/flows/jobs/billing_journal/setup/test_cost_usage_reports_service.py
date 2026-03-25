from typing import Any

import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.flows.jobs.billing_journal.setup.cost_usage_reports import (
    CostUsageReportsSetupService,
)

_BILLING_VIEW_ARN = "arn:aws:billing::123456789012:billingview/billing-transfer-test-view"


def test_create_billing_exports_creates_export_with_pm_account_id(mocker: Any) -> None:
    """Create export name using PM account, source account and billing view id."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_by_account_id.return_value = [
        {
            "arn": _BILLING_VIEW_ARN,
            "sourceAccountId": "source-account-id",
        }
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()

    service = CostUsageReportsSetupService()

    result = service.create_billing_exports(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
        fail_on_export_error=False,
    )

    assert result.created_exports == 1
    assert result.skipped_exports == 0
    assert result.failed_exports == 0
    mock_aws_client.create_billing_export.assert_called_once_with(
        billing_view_arn=_BILLING_VIEW_ARN,
        export_name="pm-account-id-source-account-id-test-view",
        s3_bucket="mpt-billing-pm-account-id",
        s3_prefix="cur-source-account-id/billing-transfer-test-view",
    )


def test_create_billing_exports_fail_on_error_flag_stops_on_error(mocker: Any) -> None:
    """Raise on export creation errors when fail_on_export_error is enabled."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN, "sourceAccountId": "mpa-account-id"}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()
    mock_aws_client.create_billing_export.side_effect = AWSError("Some AWS error")

    service = CostUsageReportsSetupService()

    with pytest.raises(AWSError) as exc_info:
        service.create_billing_exports(
            mock_aws_client,
            "pm-account-id",
            "mpa-account-id",
            fail_on_export_error=True,
        )

    assert "Failed to create billing export for view" in str(exc_info.value)


def test_create_billing_exports_logs_error_and_continues_when_fail_fast_disabled(
    mocker: Any,
) -> None:
    """Count failed exports when fail_on_export_error is disabled."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN, "sourceAccountId": "mpa-account-id"}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()
    mock_aws_client.create_billing_export.side_effect = AWSError("Some AWS error")

    service = CostUsageReportsSetupService()

    result = service.create_billing_exports(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
        fail_on_export_error=False,
    )

    assert result.created_exports == 0
    assert result.skipped_exports == 0
    assert result.failed_exports == 1


def test_create_billing_exports_skips_existing_exports(mocker: Any) -> None:
    """Skip exports already present in dedup cache."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = {_BILLING_VIEW_ARN}

    service = CostUsageReportsSetupService()

    result = service.create_billing_exports(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
    )

    assert result.created_exports == 0
    assert result.skipped_exports == 1
    assert result.failed_exports == 0
    mock_aws_client.create_billing_export.assert_not_called()


def test_create_billing_exports_handles_missing_arn_field(mocker: Any) -> None:
    """Skip billing views without arn or billingViewArn."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_by_account_id.return_value = [
        {"billingViewId": "test-view"}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = set()

    service = CostUsageReportsSetupService()

    result = service.create_billing_exports(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
    )

    assert result.created_exports == 0
    assert result.skipped_exports == 0
    assert result.failed_exports == 0
    mock_aws_client.create_billing_export.assert_not_called()


def test_create_billing_exports_dry_run_still_reads_existing_exports(mocker: Any) -> None:
    """Use AWS read calls in dry-run to keep skip/create counters accurate."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_existing_billing_exports.return_value = {_BILLING_VIEW_ARN}

    service = CostUsageReportsSetupService()

    result = service.create_billing_exports(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
        dry_run=True,
    )

    assert result.created_exports == 0
    assert result.skipped_exports == 1
    assert result.failed_exports == 0
    mock_aws_client.list_existing_billing_exports.assert_called_once_with(
        "mpt-billing-pm-account-id",
        "cur-mpa-account-id",
    )
    mock_aws_client.create_billing_export.assert_not_called()


def test_create_billing_exports_without_source_account_filter(mocker: Any) -> None:
    """Request billing views without source account filter for authorization scope."""
    mock_aws_client = mocker.Mock()
    mock_aws_client.get_all_billing_transfer_views_for_authorization_scope.return_value = []
    mock_aws_client.list_existing_billing_exports.return_value = set()

    service = CostUsageReportsSetupService()

    result = service.create_billing_exports_for_authorization(
        mock_aws_client,
        "pm-account-id",
    )

    assert result.created_exports == 0
    assert result.skipped_exports == 0
    assert result.failed_exports == 0
    mock_aws_client.get_all_billing_transfer_views_for_authorization_scope.assert_called_once_with(
        "pm-account-id"
    )


def test_run_sets_up_bucket_policy_before_creating_exports(mocker: Any) -> None:
    mock_aws_client = mocker.Mock()
    service = CostUsageReportsSetupService()
    mocker.patch.object(service, "setup_s3_bucket", return_value="created")
    mock_setup_policy = mocker.patch.object(service, "setup_s3_bucket_policy")
    mock_create_exports = mocker.patch.object(
        service,
        "create_billing_exports",
        return_value=mocker.Mock(created_exports=1, skipped_exports=0, failed_exports=0),
    )

    result = service.run(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
        fail_on_export_error=True,
        dry_run=False,
    )

    assert result.created_exports == 1
    assert result.skipped_exports == 0
    assert result.failed_exports == 0
    assert result.bucket_status == "created"
    mock_setup_policy.assert_called_once_with(
        mock_aws_client,
        "pm-account-id",
        dry_run=False,
    )
    mock_create_exports.assert_called_once_with(
        mock_aws_client,
        "pm-account-id",
        "mpa-account-id",
        fail_on_export_error=True,
        dry_run=False,
    )


def test_run_for_authorization_sets_up_bucket_policy_before_creating_exports(mocker: Any) -> None:
    mock_aws_client = mocker.Mock()
    service = CostUsageReportsSetupService()
    mocker.patch.object(service, "setup_s3_bucket", return_value="skipped")
    mock_setup_policy = mocker.patch.object(service, "setup_s3_bucket_policy")
    mock_create_exports = mocker.patch.object(
        service,
        "create_billing_exports_for_authorization",
        return_value=mocker.Mock(created_exports=0, skipped_exports=2, failed_exports=1),
    )

    result = service.run_for_authorization(
        mock_aws_client,
        "pm-account-id",
        fail_on_export_error=False,
        dry_run=False,
    )

    assert result.created_exports == 0
    assert result.skipped_exports == 2
    assert result.failed_exports == 1
    assert result.bucket_status == "skipped"
    mock_setup_policy.assert_called_once_with(
        mock_aws_client,
        "pm-account-id",
        dry_run=False,
    )
    mock_create_exports.assert_called_once_with(
        mock_aws_client,
        "pm-account-id",
        fail_on_export_error=False,
        dry_run=False,
    )
