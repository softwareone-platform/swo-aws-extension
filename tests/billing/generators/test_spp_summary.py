from decimal import Decimal

from swo_aws_extension.billing.generators.billing_report_rows import (
    ReportContext,
    build_spp_summary_row,
)
from swo_aws_extension.billing.models.invoice import InvoiceEntity, OrganizationInvoice
from swo_aws_extension.billing.models.journal_result import BillingReportRow


def _line(mocker, amount, *, is_valid=True):
    line = mocker.MagicMock()
    line.price.pp_x1 = Decimal(amount)
    line.is_valid.return_value = is_valid
    return line


def _context(currency="USD"):
    return ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", currency)


def _report_row(spp_discount, exchange_rate="1.0"):
    return BillingReportRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        service_name="EC2",
        pp=Decimal(0),
        sp=Decimal(0),
        currency="USD",
        invoice_id="INV-1",
        invoice_entity="INV-E1",
        exchange_rate=Decimal(exchange_rate),
        spp_discount=Decimal(spp_discount),
        spp_discount_pct=Decimal(0),
    )


def _organization_invoice(base_before_tax="0", payment_before_tax="0", entities=None):
    return OrganizationInvoice(
        entities=entities or {},
        base_total_amount_before_tax=Decimal(base_before_tax),
        payment_currency_total_amount_before_tax=Decimal(payment_before_tax),
    )


def _invoice_entity(exchange_rate):
    return InvoiceEntity(invoice_id="INV-1", exchange_rate=Decimal(exchange_rate))


def test_build_spp_summary_row_sp_only_sums_valid_lines(mocker):
    all_lines = [
        _line(mocker, "100.00"),
        _line(mocker, "50.00"),
        _line(mocker, "999.00", is_valid=False),
    ]

    result = build_spp_summary_row(_context(), all_lines, [], _organization_invoice())

    assert result.sp == Decimal("150.00")


def test_build_spp_summary_row_pp_uses_base_currency_before_tax_for_usd(mocker):
    organization_invoice = _organization_invoice(
        base_before_tax="97.024883950", payment_before_tax="999.00"
    )

    result = build_spp_summary_row(_context("USD"), [], [], organization_invoice)

    assert result.pp == Decimal("97.024883950")


def test_build_spp_summary_row_pp_uses_payment_currency_before_tax_for_non_usd(mocker):
    organization_invoice = _organization_invoice(
        base_before_tax="999.00", payment_before_tax="90.532488395"
    )

    result = build_spp_summary_row(_context("EUR"), [], [], organization_invoice)

    assert result.pp == Decimal("90.532488395")


def test_build_spp_summary_row_discount_sums_per_service_report_rows(mocker):
    billing_report_rows = [
        _report_row("-0.07933332540"),
        _report_row("-0.00491806710"),
    ]

    result = build_spp_summary_row(_context(), [], billing_report_rows, _organization_invoice())

    assert result.spp_discount == Decimal("-0.07933332540") + Decimal("-0.00491806710")


def test_build_spp_summary_row_exchange_rate_taken_from_invoice_entity(mocker):
    organization_invoice = _organization_invoice(
        entities={"ENT-1": _invoice_entity("0.8664846127")}
    )

    result = build_spp_summary_row(_context(), [], [], organization_invoice)

    assert result.exchange_rate == Decimal("0.8664846127")


def test_build_spp_summary_row_exchange_rate_falls_back_to_another_entity(mocker):
    organization_invoice = _organization_invoice(
        entities={
            "ENT-NO-RATE": _invoice_entity("0"),
            "ENT-WITH-RATE": _invoice_entity("0.8664846127"),
        }
    )

    result = build_spp_summary_row(_context(), [], [], organization_invoice)

    assert result.exchange_rate == Decimal("0.8664846127")


def test_build_spp_summary_row_defaults_exchange_rate_when_no_entities(mocker):
    result = build_spp_summary_row(_context(), [], [], _organization_invoice())

    assert result.exchange_rate == Decimal("1.0")


def test_build_spp_summary_row_discount_pct_uses_full_precision(mocker):
    organization_invoice = _organization_invoice(base_before_tax="90.00")
    billing_report_rows = [_report_row("-10.00")]

    result = build_spp_summary_row(_context(), [], billing_report_rows, organization_invoice)

    assert result.spp_discount_pct == Decimal("10.00") / Decimal("90.00")


def test_build_spp_summary_row_zero_pp_guards_percentage(mocker):
    billing_report_rows = [_report_row("-10.00")]

    result = build_spp_summary_row(_context(), [], billing_report_rows, _organization_invoice())

    assert result.pp == Decimal(0)
    assert result.spp_discount_pct == Decimal(0)
    assert result.markup == Decimal(0)


def test_build_spp_summary_row_markup_uses_full_precision(mocker):
    all_lines = [_line(mocker, "100.00")]
    organization_invoice = _organization_invoice(base_before_tax="90.00")

    result = build_spp_summary_row(_context(), all_lines, [], organization_invoice)

    expected_markup = (Decimal("100.00") - Decimal("90.00")) / Decimal("90.00")
    assert result.markup == expected_markup
