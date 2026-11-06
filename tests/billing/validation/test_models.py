from decimal import Decimal

from swo_aws_extension.billing.validation.models import MpaInvoices
from tests.billing.validation.conftest import MPA, build_invoice_line


def test_principal_total_prefers_invoice_with_spp_breakdown():
    invoices = MpaInvoices(
        mpa=MPA,
        currency="USD",
        lines=[
            build_invoice_line(charges="9300", spp="0", cost="9300", has_spp_breakdown=False),
            build_invoice_line(charges="1662.77", spp="-199.55", cost="0", tax="0"),
        ],
    )

    result = invoices.principal_total

    assert result == Decimal(0)


def test_principal_total_falls_back_to_first_aws_invoice():
    invoices = MpaInvoices(
        mpa=MPA,
        currency="USD",
        lines=[
            build_invoice_line(
                charges="50",
                spp="0",
                cost="50",
                billing_entity="AWS_MARKETPLACE",
                has_spp_breakdown=False,
            ),
            build_invoice_line(
                charges="100", spp="0", cost="90", tax="10", has_spp_breakdown=False
            ),
        ],
    )

    result = invoices.principal_total

    assert result == Decimal(100)


def test_principal_total_without_aws_invoices_is_zero():
    invoices = MpaInvoices(
        mpa=MPA,
        currency="USD",
        lines=[
            build_invoice_line(
                charges="50",
                spp="0",
                cost="50",
                billing_entity="AWS_MARKETPLACE",
                has_spp_breakdown=False,
            )
        ],
    )

    result = invoices.principal_total

    assert result == Decimal(0)
