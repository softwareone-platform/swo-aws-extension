from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    OrganizationInvoice,
    OrganizationInvoiceResult,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    OrganizationReport,
    OrganizationUsageResult,
)
from swo_aws_extension.flows.jobs.billing_validation.agreement_validation import (
    AgreementBillingValidator,
)
from swo_aws_extension.flows.jobs.billing_validation.results import ValidationStatus
from tests.flows.jobs.billing_validation.conftest import AGREEMENT_ID, MPA, build_invoice_summary

MODULE = "swo_aws_extension.flows.jobs.billing_validation.agreement_validation"


def _agreement(service_discount="62.5"):
    return {
        "id": AGREEMENT_ID,
        "externalIds": {"vendor": MPA},
        "parameters": {
            "fulfillment": [
                {"externalId": "channelHandshakeApproved", "value": "yes"},
                {"externalId": "serviceDiscount", "value": service_discount},
            ],
            "ordering": [],
        },
    }


@pytest.fixture
def validator():
    return AgreementBillingValidator(Decimal("5.0"))


@pytest.fixture
def invoice_result():
    return OrganizationInvoiceResult(
        raw_data=[build_invoice_summary()], invoice=OrganizationInvoice()
    )


def test_validate_returns_ok_when_journal_matches_invoices(
    validator, invoice_result, platform_summary
):
    result = validator.validate(
        _agreement(),
        OrganizationUsageResult(reports=OrganizationReport()),
        invoice_result,
        platform_summary,
    )

    assert result.status == ValidationStatus.OK
    assert result.expected.sales_price == Decimal("17046.21")


def test_validate_flags_mismatch_when_discount_differs(validator, invoice_result, platform_summary):
    result = validator.validate(
        _agreement("25"),
        OrganizationUsageResult(reports=OrganizationReport()),
        invoice_result,
        platform_summary,
    )

    assert result.status == ValidationStatus.MISMATCH
    assert [check.name for check in result.failed_checks] == ["Sales price (SP)"]


def test_validate_reports_missing_invoices(validator, platform_summary):
    result = validator.validate(
        _agreement(),
        OrganizationUsageResult(reports=OrganizationReport()),
        OrganizationInvoiceResult(),
        platform_summary,
    )

    assert result.status == ValidationStatus.MISSING_INVOICES


def test_validate_returns_none_without_summary_row(validator, invoice_result):
    result = validator.validate(
        _agreement(), OrganizationUsageResult(reports=OrganizationReport()), invoice_result, None
    )

    assert result is None


def test_validate_reports_unexpected_errors(mocker, validator, invoice_result, platform_summary):
    mocker.patch(f"{MODULE}.extract_discounts", side_effect=KeyError("parameters"))

    result = validator.validate(
        _agreement(),
        OrganizationUsageResult(reports=OrganizationReport()),
        invoice_result,
        platform_summary,
    )

    assert result.status == ValidationStatus.ERROR
    assert result.platform is platform_summary
    assert result.notes == ["KeyError: 'parameters'"]


def test_validate_converts_invoices_with_the_journal_entities(
    mocker, validator, invoice_result, platform_summary
):
    mapper_mock = mocker.patch(f"{MODULE}.InvoiceMapper")
    mapper_mock.return_value.for_mpa.return_value.lines = []

    result = validator.validate(
        _agreement(),
        OrganizationUsageResult(reports=OrganizationReport()),
        invoice_result,
        platform_summary,
    )

    assert result.status == ValidationStatus.MISSING_INVOICES
    mapper_mock.assert_called_once_with(
        invoice_result.raw_data, platform_summary.currency, invoice_result.invoice
    )
