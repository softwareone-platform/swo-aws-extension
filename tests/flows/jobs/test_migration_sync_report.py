import pytest

from swo_aws_extension.airtable.models import AccountMigrationStatus
from swo_aws_extension.flows.jobs.migration_sync_report import (
    NOTIFICATION_TITLE,
    SyncReport,
    describe_row_changes,
)

ORDER_ID = "ORD-0792-5000-2253-4210"
OTHER_ORDER_ID = "ORD-0792-5000-2253-4211"


@pytest.fixture
def mock_teams(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_report.TeamsNotificationManager"
    ).return_value


def test_describe_row_changes_uses_airtable_column_names():
    result = describe_row_changes({
        "migration_status": AccountMigrationStatus.COMPLETED,
        "migration_completed_date": "2026-09-17",
        "error": "",
    })

    assert result == [
        "Migration status: Completed",
        "Migration completed date: 2026-09-17",
        "Error: cleared",
    ]


def test_send_skips_teams_when_nothing_changed(mock_teams):
    report = SyncReport(dry_run=False, total_rows=3)

    report.send()  # act

    mock_teams.send_success.assert_not_called()
    mock_teams.send_warning.assert_not_called()


def test_send_lists_changes_per_order(mock_teams):
    report = SyncReport(dry_run=False, total_rows=3)
    report.add_row_changes(ORDER_ID, {"mpt_order_status": "Processing"})
    report.add_created_ticket(ORDER_ID, "CS0004728")
    report.add_started_onboarding(ORDER_ID, "arn:execution")
    report.updated_rows.append(ORDER_ID)
    report.add_row_changes(OTHER_ORDER_ID, {"migration_status": AccountMigrationStatus.COMPLETED})
    report.updated_rows.append(OTHER_ORDER_ID)

    report.send()  # act

    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 3. Rows updated: 2. Tickets created: 1. Onboardings started: 1. "
        "Rows with errors: 0.\n\n"
        "Changes:\n"
        f"- {ORDER_ID}: MPT Order status: Processing; "
        "Billing transfer start ticket CS0004728 created; "
        "Services onboarding started (arn:execution)\n"
        f"- {OTHER_ORDER_ID}: Migration status: Completed",
    )
    mock_teams.send_warning.assert_not_called()


def test_send_warns_with_errors_and_counts_each_failed_row_once(mock_teams):
    report = SyncReport(dry_run=False, total_rows=1)
    report.add_failed_row(ORDER_ID, "first failure")
    report.add_failed_row(ORDER_ID, "second failure")

    report.send()  # act

    assert report.has_changes is True
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 1. Rows updated: 0. Tickets created: 0. Onboardings started: 0. "
        f"Rows with errors: 1.\n\nErrors:\n- {ORDER_ID}: second failure",
    )
    mock_teams.send_success.assert_not_called()


def test_send_marks_dry_run_changes_as_not_applied(mock_teams):
    report = SyncReport(dry_run=True, total_rows=1)
    report.add_row_changes(ORDER_ID, {"mpt_order_status": "Completed"})

    report.send()  # act

    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Dry run. Rows checked: 1. Rows updated: 0. Tickets created: 0. Onboardings started: 0. "
        "Rows with errors: 0.\n\n"
        f"Changes (dry run, not applied):\n- {ORDER_ID}: MPT Order status: Completed",
    )
