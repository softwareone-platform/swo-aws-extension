from io import StringIO

from django.core.management import call_command
from freezegun import freeze_time


@freeze_time("2025-02-02")
def test_call_command_no_params():
    out = StringIO()
    err = StringIO()

    call_command("generate_billing_journals", stdout=out, stderr=err)

    output = out.getvalue()
    error_output = err.getvalue()
    assert "Running generate_billing_journals for 2025-01" in output
    assert error_output == ""


def test_call_command_with_params():
    out = StringIO()
    err = StringIO()

    call_command("generate_billing_journals", year=2025, month=3, stdout=out, stderr=err)

    output = out.getvalue()
    error_output = err.getvalue()
    assert "Running generate_billing_journals for 2025-03" in output
    assert error_output == ""


def test_test_call_command_with_error_year():
    out = StringIO()
    err = StringIO()

    call_command("generate_billing_journals", year=1998, month=3, stdout=out, stderr=err)

    output = out.getvalue()
    error_output = err.getvalue()
    assert output == ""
    assert "Year must be 2000 or higher, got 1998" in error_output


def test_test_call_command_with_error_month():
    out = StringIO()
    err = StringIO()

    call_command("generate_billing_journals", year=2020, month=13, stdout=out, stderr=err)

    output = out.getvalue()
    error_output = err.getvalue()
    assert output == ""
    assert "Month must be between 1 and 12, got 13" in error_output
