import datetime as dt
from decimal import Decimal

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.billing.generators.additional_line_processors.pls_charge import (
    PlSChargeProcessor,
)
from swo_aws_extension.billing.generators.additional_line_processors.saving_plans import (
    SavingPlansDistributionProcessor,
)
from swo_aws_extension.billing.generators.agreement import (
    AgreementJournalGenerator,
    apply_markup_to_lines,
    calculate_markup,
)
from swo_aws_extension.billing.generators.billing_report_rows import (
    ReportContext,
    build_spp_summary_row,
)
from swo_aws_extension.billing.generators.invoice import InvoiceGenerator
from swo_aws_extension.billing.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.billing.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.billing.models.context import AuthorizationContext
from swo_aws_extension.billing.models.invoice import (
    OrganizationInvoice,
    OrganizationInvoiceResult,
)
from swo_aws_extension.billing.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
    Price,
)
from swo_aws_extension.billing.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
)
from swo_aws_extension.constants import ResponsibilityTransferStatus

MODULE = "swo_aws_extension.billing.generators.agreement"

BILLING_YEAR = 2025
MONTH_BEFORE_BILLING = 9
BILLING_MONTH = 10
MONTH_AFTER_BILLING = 11


@pytest.fixture
def accepted_transfer_response():
    return {
        "ResponsibilityTransfer": {
            "Status": ResponsibilityTransferStatus.ACCEPTED,
            "StartTimestamp": dt.datetime(BILLING_YEAR, MONTH_BEFORE_BILLING, 1, tzinfo=dt.UTC),
        },
    }


@pytest.fixture
def mock_aws_client(mocker, accepted_transfer_response):
    mock = mocker.MagicMock(spec=AWSClient)
    mock.get_responsibility_transfer_details.return_value = accepted_transfer_response
    return mock


@pytest.fixture
def mock_get_responsibility_transfer_id(mocker):
    return mocker.patch(
        f"{MODULE}.get_responsibility_transfer_id",
        return_value="RT-123",
    )


@pytest.fixture
def mock_line_generator_cls(mocker):
    return mocker.patch(f"{MODULE}.JournalLineGenerator", autospec=True)


@pytest.fixture
def mock_extra_discounts_manager_cls(mocker):
    service_mock = mocker.patch(f"{MODULE}.ServiceDiscountProcessor", autospec=True)
    service_mock.return_value.process.return_value = []
    mocker.patch(
        f"{MODULE}.SupportDiscountProcessor", autospec=True
    ).return_value.process.return_value = []
    mocker.patch(
        f"{MODULE}.PlSDiscountProcessor", autospec=True
    ).return_value.process.return_value = []
    return service_mock


@pytest.fixture
def mock_pls_charge_manager_cls(mocker):
    cls_mock = mocker.patch(f"{MODULE}.PlSChargeProcessor", autospec=True)
    cls_mock.return_value.process.return_value = []
    return cls_mock


@pytest.fixture(autouse=True)
def mock_build_spp_summary_row(mocker):
    mock = mocker.patch(f"{MODULE}.build_spp_summary_row")
    mock.return_value.markup = Decimal(0)
    return mock


def _mock_journal_line(mocker):
    line = mocker.MagicMock(spec=JournalLine)
    line.price = Price(Decimal("10.0"), Decimal("10.0"))
    line.is_valid.return_value = True
    return line


def _build_agreement(support_type="ResoldSupport"):
    return {
        "id": "AGR-1",
        "externalIds": {"vendor": "MPA"},
        "parameters": {
            "ordering": [
                {"externalId": "supportType", "value": support_type},
            ],
            "fulfillment": [],
        },
    }


def _build_auth_context(mock_aws_client):
    return AuthorizationContext(
        id="AUTH-1",
        pma_account="PMA-1",
        currency="USD",
        aws_client=mock_aws_client,
    )


def test_run(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
    mock_build_spp_summary_row,
):
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement(support_type="PartnerLedSupport")
    mock_journal_line = _mock_journal_line(mocker)
    mock_discount_line = _mock_journal_line(mocker)
    mock_pls_line = _mock_journal_line(mocker)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_extra_discounts_manager_cls.return_value.process.return_value = [mock_discount_line]
    mock_pls_instance = mocker.MagicMock(spec=PlSChargeProcessor)
    mock_pls_instance.process.return_value = [mock_pls_line]
    mock_pls_charge_manager_cls.return_value = mock_pls_instance
    mock_account_usage = mocker.MagicMock(spec=AccountUsage)
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mock_account_usage}
    mock_usage_result.has_enterprise_support.return_value = True
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(),
        raw_data=[
            {"InvoiceId": "INV-001"},
            {"InvoiceId": "INV-001"},
            {"InvoiceId": "INV-002"},
            {"InvoicingEntity": "AWS Inc."},
        ],
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    assert result.lines == [mock_journal_line, mock_discount_line, mock_pls_line]
    assert result.invoice_ids == {"INV-001", "INV-002"}
    mock_invoice_generator.run.assert_called_once()
    mock_pls_instance.process.assert_called_once()
    mock_generator_instance.generate.assert_called_once_with(
        "ACC-1",
        mock_account_usage,
        mocker.ANY,
        mocker.ANY,
    )
    assert isinstance(mock_generator_instance.generate.call_args[0][2], JournalDetails)
    assert result.spp_summary_row is mock_build_spp_summary_row.return_value
    mock_build_spp_summary_row.assert_called_once_with(
        mocker.ANY,
        result.lines,
        result.billing_report_rows,
        mock_invoice_generator.run.return_value.invoice,
        mocker.ANY,
    )


def test_run_without_pls(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
):
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement(support_type="DeveloperSupport")
    mock_journal_line = _mock_journal_line(mocker)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = False
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    assert result.lines == [mock_journal_line]


def test_run_returns_empty_when_no_mpa_account(
    mocker,
    mock_context,
    mock_aws_client,
    mock_line_generator_cls,
):
    agreement = {"id": "AGR-1", "externalIds": {}, "parameters": {"ordering": []}}
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    assert result.lines == []
    assert result.report is None
    mock_usage_generator.run.assert_not_called()
    mock_invoice_generator.run.assert_not_called()
    mock_line_generator_cls.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [
        ResponsibilityTransferStatus.REQUESTED,
        ResponsibilityTransferStatus.DECLINED,
        ResponsibilityTransferStatus.CANCELED,
        ResponsibilityTransferStatus.EXPIRED,
        ResponsibilityTransferStatus.WITHDRAWN,
    ],
)
def test_run_returns_empty_when_transfer_not_accepted(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    status,
):
    agreement = _build_agreement()
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {
            "Status": status,
            "StartTimestamp": dt.datetime(
                BILLING_YEAR,
                MONTH_BEFORE_BILLING,
                1,
                tzinfo=dt.UTC,
            ),
        },
    }
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    assert result.lines == []
    assert result.report is None
    mock_usage_generator.run.assert_not_called()
    mock_invoice_generator.run.assert_not_called()


def test_run_returns_empty_when_transfer_not_started_yet(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
):
    agreement = _build_agreement()
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {
            "Status": ResponsibilityTransferStatus.ACCEPTED,
            "StartTimestamp": dt.datetime(
                BILLING_YEAR,
                MONTH_AFTER_BILLING,
                1,
                tzinfo=dt.UTC,
            ),
        },
    }
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    assert result.lines == []
    assert result.report is None
    mock_usage_generator.run.assert_not_called()
    mock_invoice_generator.run.assert_not_called()


def test_run_processes_when_transfer_started_on_billing_start(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
):
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement()
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {
            "Status": ResponsibilityTransferStatus.ACCEPTED,
            "StartTimestamp": dt.datetime(
                BILLING_YEAR,
                BILLING_MONTH,
                1,
                tzinfo=dt.UTC,
            ),
        },
    }
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = []
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = False
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    mock_invoice_generator.run.assert_called_once()
    mock_usage_generator.run.assert_called_once()
    assert result.lines is not None


def test_pls_mismatch_param_pls_but_no_enterprise_in_report(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
):
    """When param says PLS but report has no Enterprise Support, record mismatch."""
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement(support_type="PartnerLedSupport")
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = []
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = False
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)  # act

    assert len(result.pls_mismatches) == 1
    assert result.pls_mismatches[0].pls_in_order is True
    assert result.pls_mismatches[0].report_has_enterprise is False


def test_pls_mismatch_param_resold_but_enterprise_in_report(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
):
    """When param says Resold but report has Enterprise Support, record mismatch and apply PLS."""
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement(support_type="ResoldSupport")
    mock_journal_line = _mock_journal_line(mocker)
    mock_pls_line = _mock_journal_line(mocker)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_pls_instance = mocker.MagicMock(spec=PlSChargeProcessor)
    mock_pls_instance.process.return_value = [mock_pls_line]
    mock_pls_charge_manager_cls.return_value = mock_pls_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = True
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)  # act

    assert len(result.pls_mismatches) == 1
    assert result.pls_mismatches[0].pls_in_order is False
    assert result.pls_mismatches[0].report_has_enterprise is True
    mock_pls_instance.process.assert_called_once()
    assert mock_pls_line in result.lines


def test_run_with_split_billing_enabled(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
):
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    mock_sp_processor = mocker.patch(f"{MODULE}.SavingPlansDistributionProcessor", autospec=True)
    mock_sp_instance = mocker.MagicMock(spec=SavingPlansDistributionProcessor)
    mock_sp_line = _mock_journal_line(mocker)
    mock_sp_instance.process.return_value = [mock_sp_line]
    mock_sp_processor.return_value = mock_sp_instance
    agreement = {
        "id": "AGR-1",
        "externalIds": {"vendor": "MPA"},
        "parameters": {
            "ordering": [
                {"externalId": "supportType", "value": "ResoldSupport"},
            ],
            "fulfillment": [
                {"externalId": "splitBillingPolicy", "value": "LINKED_ACCOUNT_PERCENTAGE"},
            ],
        },
    }
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = []
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = False
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    mock_sp_instance.process.assert_called_once()
    assert mock_sp_line in result.lines


def _build_real_line(amount, *, error=None):
    journal_details = JournalDetails("AGR-1", "MPA", "2025-10-01", "2025-10-31")
    invoice_details = InvoiceDetails(
        service_name="EC2",
        amount=amount,
        account_id="ACC-1",
        invoice_entity="ENT-1",
        start_date="2025-10-01",
        end_date="2025-10-31",
        error=error,
    )
    return JournalLine.build(
        item_external_id="ITEM-1", journal_details=journal_details, invoice_details=invoice_details
    )


def test_run_applies_markup_to_valid_line_prices(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
    mock_build_spp_summary_row,
):
    mock_build_spp_summary_row.side_effect = build_spp_summary_row
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement(support_type="DeveloperSupport")
    real_line = _build_real_line(Decimal("100.00"))
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [real_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = False
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(base_total_amount_before_tax=Decimal("50.00")),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)  # act

    # sp = 100.00 (the only valid line), pp = 50.00 -> markup = 1.0 -> divisor = 2.0
    assert result.spp_summary_row.markup == Decimal("1.0")
    assert result.lines[0].price.pp_x1 == Decimal("50.00")
    assert result.lines[0].price.unit_pp == Decimal("50.00")


def test_run_skips_rescale_when_markup_divisor_not_positive(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
    mock_build_spp_summary_row,
):
    mock_build_spp_summary_row.side_effect = build_spp_summary_row
    mock_builder = mocker.MagicMock()
    mock_builder.build.return_value = []
    mock_builder.build_by_account.return_value = []
    mocker.patch(f"{MODULE}.BillingReportRowsBuilder", return_value=mock_builder)
    agreement = _build_agreement(support_type="DeveloperSupport")
    real_line = _build_real_line(Decimal("0.00"))
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [real_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mocker.MagicMock(spec=AccountUsage)}
    mock_usage_result.has_enterprise_support.return_value = False
    mock_usage_generator.run.return_value = mock_usage_result
    mock_invoice_generator = mocker.MagicMock(spec=InvoiceGenerator)
    mock_invoice_generator.run.return_value = OrganizationInvoiceResult(
        invoice=OrganizationInvoice(base_total_amount_before_tax=Decimal("50.00")),
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)  # act

    # sp = 0.00, pp = 50.00 -> markup = -1.0 -> divisor = 0 -> rescale is skipped
    assert result.spp_summary_row.markup == Decimal("-1.0")
    assert result.lines[0].price.pp_x1 == Decimal("0.00")


def _markup_context(currency="USD"):
    return ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", currency)


def _markup_organization_invoice(base_before_tax="0", payment_before_tax="0"):
    return OrganizationInvoice(
        base_total_amount_before_tax=Decimal(base_before_tax),
        payment_currency_total_amount_before_tax=Decimal(payment_before_tax),
    )


def _markup_line(mocker, amount, *, is_valid=True):
    line = mocker.MagicMock()
    line.price.pp_x1 = Decimal(amount)
    line.is_valid.return_value = is_valid
    return line


def _markup_journal_line(amount, *, error=None):
    journal_details = JournalDetails("AGR-1", "MPA-1", "2025-10-01", "2025-10-31")
    invoice_details = InvoiceDetails(
        service_name="EC2",
        amount=amount,
        account_id="ACC-1",
        invoice_entity="ENT-1",
        start_date="2025-10-01",
        end_date="2025-10-31",
        error=error,
    )
    return JournalLine.build(
        item_external_id="ITEM-1", journal_details=journal_details, invoice_details=invoice_details
    )


def test_calculate_markup_uses_full_precision(mocker):
    all_lines = [_markup_line(mocker, "100.00")]
    organization_invoice = _markup_organization_invoice(base_before_tax="90.00")

    result = calculate_markup(all_lines, organization_invoice, _markup_context())  # act

    expected_markup = (Decimal("100.00") - Decimal("90.00")) / Decimal("90.00")
    assert result == expected_markup


def test_calculate_markup_uses_payment_currency_before_tax_for_non_usd(mocker):
    all_lines = [_markup_line(mocker, "100.00")]
    organization_invoice = _markup_organization_invoice(
        base_before_tax="999.00", payment_before_tax="50.00"
    )

    result = calculate_markup(all_lines, organization_invoice, _markup_context("EUR"))  # act

    expected_markup = (Decimal("100.00") - Decimal("50.00")) / Decimal("50.00")
    assert result == expected_markup


def test_calculate_markup_defaults_to_zero_when_pp_is_zero(mocker):
    all_lines = [_markup_line(mocker, "100.00")]

    result = calculate_markup(all_lines, _markup_organization_invoice(), _markup_context())  # act

    assert result == Decimal(0)


def test_calculate_markup_only_sums_valid_lines(mocker):
    all_lines = [
        _markup_line(mocker, "100.00"),
        _markup_line(mocker, "999.00", is_valid=False),
    ]
    organization_invoice = _markup_organization_invoice(base_before_tax="90.00")

    result = calculate_markup(all_lines, organization_invoice, _markup_context())  # act

    expected_markup = (Decimal("100.00") - Decimal("90.00")) / Decimal("90.00")
    assert result == expected_markup


def test_apply_markup_to_lines_rescales_valid_lines():
    line = _markup_journal_line(Decimal("100.00"))

    apply_markup_to_lines([line], Decimal("1.0"))  # act

    assert line.price.pp_x1 == Decimal("50.00")
    assert line.price.unit_pp == Decimal("50.00")


def test_apply_markup_to_lines_skips_invalid_lines():
    line = _markup_journal_line(Decimal("100.00"), error="Some error")

    apply_markup_to_lines([line], Decimal("1.0"))  # act

    assert line.price.pp_x1 == Decimal("100.00")
    assert line.price.unit_pp == Decimal("100.00")


def test_apply_markup_to_lines_skips_rescale_when_divisor_not_positive():
    line = _markup_journal_line(Decimal("100.00"))

    apply_markup_to_lines([line], Decimal(-1))  # act

    assert line.price.pp_x1 == Decimal("100.00")
    assert line.price.unit_pp == Decimal("100.00")


def test_apply_markup_to_lines_rounds_to_six_decimal_places():
    original_amount = Decimal("0.097533806")
    divisor = Decimal("1.0107594")
    line = _markup_journal_line(original_amount)

    apply_markup_to_lines([line], Decimal("0.0107594"))  # act

    expected = round(original_amount / divisor, 6)
    assert line.price.pp_x1 == expected
    assert line.price.pp_x1.as_tuple().exponent >= -6
    assert line.price.unit_pp.as_tuple().exponent >= -6
