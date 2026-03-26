from io import StringIO

import pytest
from django.core.management import call_command
from freezegun import freeze_time

from swo_aws_extension.constants import (
    COMMAND_INVALID_BILLING_DATE,
    COMMAND_INVALID_BILLING_DATE_FUTURE,
    BillingJournalUsageSourceEnum,
)

MODULE = "swo_aws_extension.management.commands.generate_billing_journals"

VALID_YEAR = 2025
FUTURE_YEAR = 2026


@pytest.fixture
def mock_service(mocker):
    return mocker.patch(
        f"{MODULE}.BillingJournalService",
        autospec=True,
    )


@pytest.fixture
def command_output():
    return {"out": StringIO(), "err": StringIO()}


def _get_output(command_output):
    return command_output["out"].getvalue(), command_output["err"].getvalue()


@freeze_time("2026-01-05 00:00:00")
def test_command_no_params_uses_previous_month(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Start generate_billing_journals for 2025-12 (all)" in output
    assert not error_output
    mock_service.return_value.run.assert_called_once()


@freeze_time("2025-02-04 23:59:59")
def test_command_previous_month_before_day_five_fails(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert COMMAND_INVALID_BILLING_DATE in error_output
    mock_service.return_value.run.assert_not_called()


@freeze_time("2025-02-08 23:59:59")
def test_command_future_date_fails(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        year=FUTURE_YEAR,
        month=1,
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert COMMAND_INVALID_BILLING_DATE_FUTURE in error_output
    mock_service.return_value.run.assert_not_called()


@freeze_time("2025-02-09 23:59:59")
def test_command_current_month_fails(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        year=VALID_YEAR,
        month=2,
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert COMMAND_INVALID_BILLING_DATE_FUTURE in error_output
    mock_service.return_value.run.assert_not_called()


def test_command_with_valid_year_and_month(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        year=VALID_YEAR,
        month=3,
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Start generate_billing_journals for 2025-03 (all)" in output
    assert not error_output
    mock_service.return_value.run.assert_called_once()


@pytest.mark.parametrize(
    ("year", "expected_error"),
    [
        (1998, "Year must be 2025 or higher, got 1998"),
        (2024, "Year must be 2025 or higher, got 2024"),
    ],
)
def test_command_with_invalid_year_fails(
    mock_service,
    command_output,
    year,
    expected_error,
):
    result = call_command(
        "generate_billing_journals",
        year=year,
        month=3,
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert expected_error in error_output
    mock_service.return_value.run.assert_not_called()


@pytest.mark.parametrize("month", [0, 13, -1, 100])
def test_command_with_invalid_month_fails(mock_service, command_output, month):
    result = call_command(
        "generate_billing_journals",
        year=VALID_YEAR,
        month=month,
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert f"Invalid month. Must be between 1 and 12. Got {month}." in error_output
    mock_service.return_value.run.assert_not_called()


@freeze_time("2025-07-07 23:59:59")
def test_command_with_one_authorization(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        authorizations=["AUT-123-123-123"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Start generate_billing_journals for 2025-06 (AUT-123-123-123)" in output
    assert not error_output
    mock_service.return_value.run.assert_called_once()


@freeze_time("2025-07-07 23:59:59")
def test_command_with_multiple_authorizations(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        authorizations=["AUT-123-123-001", "AUT-123-123-002"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "AUT-123-123-001 AUT-123-123-002" in output
    assert not error_output
    mock_service.return_value.run.assert_called_once()


@freeze_time("2025-07-07 23:59:59")
@pytest.mark.parametrize("usage_source", [source.value for source in BillingJournalUsageSourceEnum])
def test_command_with_valid_usage_source(mock_service, command_output, usage_source):
    result = call_command(
        "generate_billing_journals",
        year=VALID_YEAR,
        month=3,
        usage_source=usage_source,
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert "Start generate_billing_journals for 2025-03 (all)" in output
    assert not error_output
    mock_service.return_value.run.assert_called_once()


@freeze_time("2025-07-07 23:59:59")
def test_command_with_invalid_usage_source_fails(command_output):
    with pytest.raises(ValueError, match="is not a valid BillingJournalUsageSourceEnum"):
        call_command(
            "generate_billing_journals",
            year=VALID_YEAR,
            month=3,
            usage_source="invalid_source",
            stdout=command_output["out"],
            stderr=command_output["err"],
        )


@freeze_time("2025-07-07 23:59:59")
def test_command_with_invalid_authorization_fails(mock_service, command_output):
    result = call_command(
        "generate_billing_journals",
        authorizations=["AUT-123-123-001", "PRD-123-123-002"],
        stdout=command_output["out"],
        stderr=command_output["err"],
    )

    assert result is None
    output, error_output = _get_output(command_output)
    assert not output
    assert "Invalid authorizations id:" in error_output
    assert "PRD-123-123-002" in error_output
    mock_service.return_value.run.assert_not_called()
