from io import StringIO
from typing import Any

from django.core.management import call_command

from swo_aws_extension.aws.errors import AWSError

MODULE = "swo_aws_extension.management.commands.setup_cost_usage_reports"
MODULE_BY_AUTH = "swo_aws_extension.management.commands.setup_cost_usage_reports_by_authorizations"


def _get_output(command_output: dict[str, StringIO]) -> tuple[str, str]:
    return command_output["out"].getvalue(), command_output["err"].getvalue()


def test_command_runs_for_selected_authorization_and_agreement(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE}.get_authorizations")
    mock_authorizations.return_value = [
        {
            "id": "AUT-123-123-123",
            "externalIds": {"operations": "651706759263"},
        }
    ]
    mock_agreements = mocker.patch(f"{MODULE}.get_agreements_by_query")
    mock_agreements.return_value = [
        {
            "id": "AGR-123-123-123",
            "externalIds": {"vendor": "225989344502"},
        }
    ]
    mock_aws_client_class = mocker.patch(f"{MODULE}.AWSClient", autospec=True)
    mock_service_class = mocker.patch(f"{MODULE}.CostUsageReportsSetupService", autospec=True)
    mock_service_class.return_value.run.return_value = mocker.Mock(
        created_exports=1,
        skipped_exports=2,
        failed_exports=0,
        bucket_status="created",
    )
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports",
        authorizations=["AUT-123-123-123"],
        agreements=["AGR-123-123-123"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Processing authorization AUT-123-123-123 agreement AGR-123-123-123" in output
    assert (
        "S3 bucket: mpt-billing-651706759263 created and is owned by 651706759263 account" in output
    )
    assert "Processing setup_cost_usage_reports completed." in output
    assert not error_output
    mock_aws_client_class.assert_called_once()
    mock_service_class.return_value.run.assert_called_once_with(
        mock_aws_client_class.return_value,
        "651706759263",
        "225989344502",
        fail_on_export_error=True,
        dry_run=False,
    )


def test_command_fail_fast_on_first_setup_error(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE}.get_authorizations")
    mock_authorizations.return_value = [
        {
            "id": "AUT-123-123-123",
            "externalIds": {"operations": "651706759263"},
        },
        {
            "id": "AUT-123-123-124",
            "externalIds": {"operations": "651706759263"},
        },
    ]
    mock_agreements = mocker.patch(f"{MODULE}.get_agreements_by_query")
    mock_agreements.side_effect = [
        [{"id": "AGR-123-123-123", "externalIds": {"vendor": "225989344502"}}],
        [{"id": "AGR-123-123-124", "externalIds": {"vendor": "225989344502"}}],
    ]
    mocker.patch(f"{MODULE}.AWSClient", autospec=True)
    mock_service_class = mocker.patch(f"{MODULE}.CostUsageReportsSetupService", autospec=True)
    mock_service_class.return_value.run.side_effect = AWSError("boom")
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Start processing setup_cost_usage_reports" in output
    assert "Partial summary - processed: 1, completed: 0" in error_output
    assert "Processing setup_cost_usage_reports completed." not in output
    assert mock_service_class.return_value.run.call_count == 1


def test_command_prints_bucket_skipped_message(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE}.get_authorizations")
    mock_authorizations.return_value = [
        {
            "id": "AUT-123-123-123",
            "externalIds": {"operations": "651706759263"},
        }
    ]
    mock_agreements = mocker.patch(f"{MODULE}.get_agreements_by_query")
    mock_agreements.return_value = [
        {
            "id": "AGR-123-123-123",
            "externalIds": {"vendor": "225989344502"},
        }
    ]
    mocker.patch(f"{MODULE}.AWSClient", autospec=True)
    mock_service_class = mocker.patch(f"{MODULE}.CostUsageReportsSetupService", autospec=True)
    mock_service_class.return_value.run.return_value = mocker.Mock(
        created_exports=0,
        skipped_exports=1,
        failed_exports=0,
        bucket_status="skipped",
    )
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert (
        "S3 bucket: mpt-billing-651706759263 already exists and is owned by 651706759263 account"
        in output
    )
    assert not error_output


def test_command_invalid_agreement_id_fails(mocker: Any) -> None:
    mocker.patch(f"{MODULE}.get_authorizations")
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports",
        agreements=["INVALID-1"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert "Invalid agreements id: INVALID-1" in error_output


def test_command_no_authorizations_found(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE}.get_authorizations")
    mock_authorizations.return_value = []
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "No authorizations found" in output
    assert "Processing setup_cost_usage_reports completed." in output
    assert not error_output


def test_command_by_authorization_runs_for_selected_authorization(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE_BY_AUTH}.get_authorizations")
    mock_authorizations.return_value = [
        {
            "id": "AUT-123-123-123",
            "externalIds": {"operations": "651706759263"},
        }
    ]
    mock_aws_client_class = mocker.patch(f"{MODULE_BY_AUTH}.AWSClient", autospec=True)
    mock_service_class = mocker.patch(
        f"{MODULE_BY_AUTH}.CostUsageReportsSetupService", autospec=True
    )
    mock_service_class.return_value.run_for_authorization.return_value = mocker.Mock(
        created_exports=1,
        skipped_exports=2,
        failed_exports=0,
        bucket_status="created",
    )
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports_by_authorizations",
        authorizations=["AUT-123-123-123"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Processing authorization AUT-123-123-123 using PM account 651706759263" in output
    assert "Processing setup_cost_usage_reports_by_authorizations completed." in output
    assert not error_output
    mock_aws_client_class.assert_called_once()
    mock_service_class.return_value.run_for_authorization.assert_called_once_with(
        mock_aws_client_class.return_value,
        "651706759263",
        fail_on_export_error=False,
        dry_run=False,
    )


def test_command_by_authorization_fail_fast_on_first_setup_error(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE_BY_AUTH}.get_authorizations")
    mock_authorizations.return_value = [
        {
            "id": "AUT-123-123-123",
            "externalIds": {"operations": "651706759263"},
        },
        {
            "id": "AUT-123-123-124",
            "externalIds": {"operations": "651706759263"},
        },
    ]
    mocker.patch(f"{MODULE_BY_AUTH}.AWSClient", autospec=True)
    mock_service_class = mocker.patch(
        f"{MODULE_BY_AUTH}.CostUsageReportsSetupService", autospec=True
    )
    mock_service_class.return_value.run_for_authorization.side_effect = AWSError("boom")
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports_by_authorizations",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Start processing setup_cost_usage_reports_by_authorizations" in output
    assert "Partial summary - processed: 1, completed: 0" in error_output
    assert "Processing setup_cost_usage_reports_by_authorizations completed." not in output
    assert mock_service_class.return_value.run_for_authorization.call_count == 1


def test_command_by_authorization_continues_when_export_creation_fails(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE_BY_AUTH}.get_authorizations")
    mock_authorizations.return_value = [
        {
            "id": "AUT-123-123-123",
            "externalIds": {"operations": "651706759263"},
        },
        {
            "id": "AUT-123-123-124",
            "externalIds": {"operations": "651706759264"},
        },
    ]
    mock_aws_client_class = mocker.patch(f"{MODULE_BY_AUTH}.AWSClient", autospec=True)
    mock_service_class = mocker.patch(
        f"{MODULE_BY_AUTH}.CostUsageReportsSetupService", autospec=True
    )
    mock_service_class.return_value.run_for_authorization.side_effect = [
        mocker.Mock(
            created_exports=0,
            skipped_exports=0,
            failed_exports=1,
            bucket_status="skipped",
        ),
        mocker.Mock(
            created_exports=2,
            skipped_exports=1,
            failed_exports=0,
            bucket_status="created",
        ),
    ]
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports_by_authorizations",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Completed authorization AUT-123-123-123: 0 created, 0 skipped, 1 failed" in output
    assert "Completed authorization AUT-123-123-124: 2 created, 1 skipped, 0 failed" in output
    assert "Processing setup_cost_usage_reports_by_authorizations completed." in output
    assert not error_output
    assert mock_service_class.return_value.run_for_authorization.call_count == 2
    mock_service_class.return_value.run_for_authorization.assert_any_call(
        mock_aws_client_class.return_value,
        "651706759263",
        fail_on_export_error=False,
        dry_run=False,
    )


def test_command_by_authorization_invalid_authorization_id_fails(mocker: Any) -> None:
    mocker.patch(f"{MODULE_BY_AUTH}.get_authorizations")
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports_by_authorizations",
        authorizations=["INVALID-1"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert "Invalid authorizations id: INVALID-1" in error_output


def test_command_by_authorization_no_authorizations_found(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE_BY_AUTH}.get_authorizations")
    mock_authorizations.return_value = []
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports_by_authorizations",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "No authorizations found" in output
    assert "Processing setup_cost_usage_reports_by_authorizations completed." in output
    assert not error_output


def test_command_by_authorization_without_operations_external_id_fails(mocker: Any) -> None:
    mock_authorizations = mocker.patch(f"{MODULE_BY_AUTH}.get_authorizations")
    mock_authorizations.return_value = [{"id": "AUT-123-123-123", "externalIds": {}}]
    command_output = {"out": StringIO(), "err": StringIO()}

    result = call_command(
        "setup_cost_usage_reports_by_authorizations",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Processing setup_cost_usage_reports_by_authorizations completed." not in output
    assert "Authorization AUT-123-123-123 has no operations external id configured" in error_output
    assert "Partial summary - processed: 0, completed: 0" in error_output
