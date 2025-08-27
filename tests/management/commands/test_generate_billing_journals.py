from io import StringIO

from django.core.management import call_command
from freezegun import freeze_time

from swo_aws_extension.constants import (
    COMMAND_INVALID_BILLING_DATE,
    COMMAND_INVALID_BILLING_DATE_FUTURE,
)


@freeze_time("2026-01-05 00:00:00")
def test_call_command_no_params(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", stdout=out, stderr=err)
    output = out.getvalue()
    error_output = err.getvalue()
    assert "Running generate_billing_journals for 2025-12" in output
    assert not error_output


@freeze_time("2025-02-04 23:59:59")
def test_call_command_wrong_date(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", stdout=out, stderr=err)
    output = out.getvalue()
    error_output = err.getvalue()
    assert not output
    assert COMMAND_INVALID_BILLING_DATE in error_output


@freeze_time("2025-02-08 23:59:59")
def test_call_command_future_date(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", stdout=out, stderr=err, year=2026, month=1)
    output = out.getvalue()
    error_output = err.getvalue()
    assert not output
    assert COMMAND_INVALID_BILLING_DATE_FUTURE in error_output


@freeze_time("2025-02-09 23:59:59")
def test_call_command_current_month(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", stdout=out, stderr=err, year=2025, month=2)
    output = out.getvalue()
    error_output = err.getvalue()
    assert not output
    assert COMMAND_INVALID_BILLING_DATE in error_output


def test_call_command_with_params(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", year=2025, month=3, stdout=out, stderr=err)
    output = out.getvalue()
    error_output = err.getvalue()
    assert "Running generate_billing_journals for 2025-03" in output
    assert not error_output


def test_test_call_command_with_error_year(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", year=1998, month=3, stdout=out, stderr=err)
    output = out.getvalue()
    error_output = err.getvalue()
    assert not output
    assert "Year must be 2025 or higher, got 1998" in error_output


def test_test_call_command_with_error_month(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command("generate_billing_journals", year=2025, month=13, stdout=out, stderr=err)
    output = out.getvalue()
    error_output = err.getvalue()
    assert not output
    assert "Invalid month. Month must be between 1 and 12. Got 13 instead." in error_output


@freeze_time("2025-07-07 23:59:59")
def test_call_command_with_one_authorization(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command(
        "generate_billing_journals", authorizations=["AUT-123-123-123"], stdout=out, stderr=err
    )
    output = out.getvalue()
    error_output = err.getvalue()
    assert (
        "Running generate_billing_journals for 2025-06 for authorizations AUT-123-123-123" in output
    )
    assert "" in error_output


@freeze_time("2025-07-07 23:59:59")
def test_call_command_with_multiple_authorization(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command(
        "generate_billing_journals",
        authorizations=["AUT-123-123-001", "AUT-123-123-002"],
        stdout=out,
        stderr=err,
    )
    output = out.getvalue()
    error_output = err.getvalue()
    assert (
        "Running generate_billing_journals for 2025-06 for "
        "authorizations AUT-123-123-001 AUT-123-123-002" in output
    )
    assert "" in error_output


@freeze_time("2025-07-07 23:59:59")
def test_call_command_with_invalid_authorization(mocker):
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.BillingJournalGenerator.generate_billing_journals",
        return_value=None,
    )
    out = StringIO()
    err = StringIO()
    call_command(
        "generate_billing_journals",
        authorizations=["AUT-123-123-001", "PRD-123-123-002"],
        stdout=out,
        stderr=err,
    )
    error_output = err.getvalue()
    assert "Invalid authorizations id: " in error_output
    assert "PRD-123-123-002" in error_output
