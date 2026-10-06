"""Rows of the ``Validation detail`` sheet: steps and invoices behind each validation."""

from decimal import Decimal

from swo_aws_extension.billing.validation.cells import amount
from swo_aws_extension.billing.validation.models import InvoiceLine
from swo_aws_extension.billing.validation.results import (
    AgreementValidation,
    DiscountStep,
    ExpectedBilling,
)

VALIDATION_DETAIL_HEADERS = (
    "Authorization ID",
    "Agreement ID",
    "MPA",
    "Currency",
    "Type",
    "Description",
    "Percentage",
    "Base",
    "Amount",
    "Invoice ID",
    "Invoice type",
    "Exchange rate",
)
STEP_TYPE = "Step"
EMPTY_TAIL = ("", "", "", "", "", "")
INVOICE_TYPE = "Invoice"
NOTE_TYPE = "Note"


def build_validation_detail_rows(validations: list[AgreementValidation]) -> list[list]:
    """Steps, invoices and notes of every validation, grouped by agreement."""
    rows: list[list] = []
    for validation in validations:
        rows.extend(_detail_rows(validation))
    return rows


def _detail_rows(validation: AgreementValidation) -> list[list]:
    prefix = [
        validation.authorization_id,
        validation.agreement_id,
        validation.mpa,
        validation.currency,
    ]
    expected = validation.expected
    rows = []
    if expected is not None:
        rows.extend(_step_rows(prefix, expected))
    if expected is not None and expected.invoices is not None:
        rows.extend(_invoice_row(prefix, line) for line in expected.invoices.lines)
    rows.extend(_note_row(prefix, note) for note in validation.notes)
    return rows


def _note_row(prefix: list, note: str) -> list:
    return [*prefix, NOTE_TYPE, note, *EMPTY_TAIL]


def _step_rows(prefix: list, expected: ExpectedBilling) -> list[list]:
    rows = [_step_row(prefix, "AWS cost price (invoice total before tax)", expected.cost_price)]
    spp_kept = expected.sales_price - expected.cost_price - expected.total_discounts
    if spp_kept:
        rows.append(_step_row(prefix, "SPP discount kept by SWO", spp_kept))
    rows.extend(_discount_row(prefix, step) for step in expected.steps)
    rows.append(_step_row(prefix, "Expected sales price", expected.sales_price))
    return rows


def _discount_row(prefix: list, step: DiscountStep) -> list:
    return [
        *prefix,
        STEP_TYPE,
        step.description,
        amount(step.percentage or None),
        amount(abs(step.base)),
        amount(step.amount),
        "",
        "",
        "",
    ]


def _step_row(prefix: list, description: str, total: Decimal) -> list:
    return [*prefix, STEP_TYPE, description, "", "", amount(total), "", "", ""]


def _invoice_row(prefix: list, line: InvoiceLine) -> list:
    return [
        *prefix,
        INVOICE_TYPE,
        f"{line.category}: charges {line.charges:.2f}, SPP {line.spp_discount:.2f}",
        "",
        amount(line.charges),
        amount(line.cost),
        line.invoice_id,
        line.invoice_type,
        amount(line.exchange_rate),
    ]
