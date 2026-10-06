from decimal import Decimal

import pytest

from swo_aws_extension.billing.models.journal_result import (
    OrganizationSppSummaryRow,
)
from swo_aws_extension.billing.validation.models import (
    AgreementDiscounts,
    InvoiceLine,
    MpaInvoices,
    ServiceSplit,
)

MPA = "740386694475"
PMA = "048153622962"
AGREEMENT_ID = "AGR-8914-6869-5020"


def build_invoice_summary(
    invoice_id="2847784289",
    mpa=MPA,
    subtotal="19295.13",
    spp="-1414.24",
    total_before_tax="16515.87",
    total="16515.87",
    billing_entity="AWS",
    payment=None,
):
    """Build an AWS invoice summary as returned by list_invoice_summaries."""
    summary = {
        "AccountId": PMA,
        "InvoiceId": invoice_id,
        "BillSourceAccounts": [mpa],
        "InvoiceType": "INVOICE",
        "Entity": {"InvoicingEntity": "Amazon Web Services, Inc.", "BillingEntity": billing_entity},
        "BaseCurrencyAmount": {
            "CurrencyCode": "USD",
            "TotalAmount": total,
            "TotalAmountBeforeTax": total_before_tax,
            "AmountBreakdown": {
                "SubTotalAmount": subtotal,
                "Discounts": {
                    "Breakdown": [{"Description": "Discount (AWS SPP Discount)", "Amount": spp}],
                },
            },
        },
    }
    if payment:
        summary["PaymentCurrencyAmount"] = payment
    return summary


def build_invoice_line(
    charges="19295.13",
    spp="-1414.24",
    cost="16515.87",
    billing_entity="AWS",
    tax="0",
    exchange_rate="1",
    *,
    has_spp_breakdown=True,
):
    return InvoiceLine(
        invoice_id="2847784289",
        invoicing_entity="Amazon Web Services, Inc.",
        billing_entity=billing_entity,
        invoice_type="INVOICE",
        charges=Decimal(charges),
        spp_discount=Decimal(spp),
        other_adjustments=Decimal(cost) - Decimal(charges) - Decimal(spp),
        cost=Decimal(cost),
        tax=Decimal(tax),
        currency="USD",
        exchange_rate=Decimal(exchange_rate),
        base_currency="USD",
        has_spp_breakdown=has_spp_breakdown,
    )


@pytest.fixture
def mpa_invoices():
    return MpaInvoices(mpa=MPA, currency="USD", lines=[build_invoice_line()])


@pytest.fixture
def discounts():
    return AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        authorization_id="AUT-7443-3939",
        handshake_approved=True,
        service_discount=Decimal("62.5"),
    )


@pytest.fixture
def service_split():
    return ServiceSplit(
        enterprise_support_charge=Decimal("206.11"),
        enterprise_support_spp=Decimal("-82.45"),
        usage_base=Decimal("14142.30"),
    )


@pytest.fixture
def platform_summary():
    return OrganizationSppSummaryRow(
        authorization_id="AUT-7443-3939",
        pma=PMA,
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        pp=Decimal("16515.87"),
        sp=Decimal("17046.2095703969"),
        currency="USD",
        exchange_rate=Decimal(1),
        spp_discount=Decimal("-1414.2392703139"),
        spp_discount_pct=Decimal("0.0856"),
        list_price=Decimal("19295.13"),
        markup=Decimal("0.0321109072907997"),
    )
