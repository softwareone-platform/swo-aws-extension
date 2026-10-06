"""Rows of the ``Validation`` sheet added to the monthly billing report.

One compact row per agreement: identification, the two checks (PP and SP) with their
difference, the discounts applied with percentage and amount in the agreement
currency, and informative columns (SPP, list price, invoices, exchange rate). Steps
and invoices are detailed in the ``Validation detail`` sheet.
"""

from decimal import Decimal

from swo_aws_extension.billing.validation.cells import amount
from swo_aws_extension.billing.validation.results import (
    AgreementValidation,
    DiscountKind,
    ValidationStatus,
)
from swo_aws_extension.billing.validation.validator import (
    COST_PRICE_CHECK,
    SALES_PRICE_CHECK,
)

DISCOUNT_HEADERS = (
    "Handshake approved",
    "Service discount %",
    "Service discount",
    "Support discount %",
    "Support discount",
    "PLS discount %",
    "PLS discount",
    "PLS support adjustment",
    "Total discounts",
)
VALIDATION_HEADERS = (
    "Authorization ID",
    "Authorization",
    "PMA",
    "Client",
    "Agreement ID",
    "Agreement",
    "MPA",
    "Currency",
    "Status",
    "Likely cause",
    "Invoice cost price",
    "Platform PP",
    "PP diff",
    "Expected SP",
    "Platform SP",
    "SP diff",
    "Tolerance",
    *DISCOUNT_HEADERS,
    "Invoice SPP discount",
    "Platform SPP discount",
    "Invoice list price",
    "Platform list price",
    "Platform markup %",
    "Invoices",
    "Exchange rate",
    "Exchange rate source",
    "Notes",
)
HUNDRED = Decimal(100)


def _sort_key(validation: AgreementValidation) -> tuple[bool, Decimal]:
    sales_check = validation.check(SALES_PRICE_CHECK)
    diff = abs(sales_check.diff) if sales_check else Decimal(0)
    return (validation.status == ValidationStatus.OK, -diff)


def build_validation_rows(validations: list[AgreementValidation]) -> list[list]:
    """One row per agreement, mismatches first and the largest SP difference on top."""
    return [_row(validation) for validation in sorted(validations, key=_sort_key)]


def _row(validation: AgreementValidation) -> list:
    return [
        *_context_cells(validation),
        *_price_cells(validation),
        *_discount_cells(validation),
        *_info_cells(validation),
        " | ".join(validation.notes),
    ]


def _context_cells(validation: AgreementValidation) -> list:
    return [
        validation.authorization_id,
        validation.names.authorization_name,
        validation.pma,
        validation.names.client_name,
        validation.agreement_id,
        validation.names.agreement_name,
        validation.mpa,
        validation.currency,
        validation.status.value,
        validation.likely_cause,
    ]


def _price_cells(validation: AgreementValidation) -> list:
    expected = validation.expected
    platform = validation.platform
    cost_check = validation.check(COST_PRICE_CHECK)
    sales_check = validation.check(SALES_PRICE_CHECK)
    return [
        amount(expected.cost_price if expected else None),
        amount(platform.pp if platform else None),
        amount(cost_check.diff if cost_check else None),
        amount(expected.sales_price if expected else None),
        amount(platform.sp if platform else None),
        amount(sales_check.diff if sales_check else None),
        amount(validation.tolerance),
    ]


def _discount_cells(validation: AgreementValidation) -> list:
    expected = validation.expected
    if expected is None:
        return ["" for _ in DISCOUNT_HEADERS]
    discounts = expected.discounts
    return [
        discounts.handshake_label if discounts else "",
        amount(expected.step_percentage(DiscountKind.SERVICE)),
        amount(expected.step_amount(DiscountKind.SERVICE)),
        amount(expected.step_percentage(DiscountKind.SUPPORT)),
        amount(expected.step_amount(DiscountKind.SUPPORT)),
        amount(expected.step_percentage(DiscountKind.PLS_DISCOUNT)),
        amount(expected.step_amount(DiscountKind.PLS_DISCOUNT)),
        amount(expected.step_amount(DiscountKind.PLS_SUPPORT_REMOVED, DiscountKind.PLS_CHARGE)),
        amount(expected.total_discounts),
    ]


def _info_cells(validation: AgreementValidation) -> list:
    expected = validation.expected
    platform = validation.platform
    invoices = expected.invoices if expected else None
    return [
        amount(expected.spp_discount if expected else None),
        amount(platform.spp_discount if platform else None),
        amount(expected.list_price if expected else None),
        amount(platform.list_price if platform else None),
        amount(platform.markup * HUNDRED if platform else None),
        invoices.invoice_ids if invoices else "",
        amount(invoices.exchange_rate if invoices else None),
        invoices.exchange_rate_source if invoices else "",
    ]
