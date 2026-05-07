import datetime as dt

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.discount.extra_discounts import (
    ExtraDiscountsManager,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.pls_charge_manager import (
    PlSChargeManager,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import AuthorizationContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    OrganizationInvoice,
    OrganizationInvoiceResult,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
)

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.agreement"

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
    return mocker.patch(f"{MODULE}.ExtraDiscountsManager", autospec=True)


@pytest.fixture
def mock_pls_charge_manager_cls(mocker):
    return mocker.patch(f"{MODULE}.PlSChargeManager", autospec=True)


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
):
    mocker.patch(f"{MODULE}.generate_billing_report_rows", return_value=[])
    agreement = _build_agreement(support_type="PartnerLedSupport")
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_discount_line = mocker.MagicMock(spec=JournalLine)
    mock_pls_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_discounts_instance = mocker.MagicMock(spec=ExtraDiscountsManager)
    mock_discounts_instance.process.return_value = [mock_discount_line]
    mock_extra_discounts_manager_cls.return_value = mock_discounts_instance
    mock_pls_instance = mocker.MagicMock(spec=PlSChargeManager)
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
    )
    generator = AgreementJournalGenerator(
        _build_auth_context(mock_aws_client),
        mock_context,
        mock_usage_generator,
        mock_invoice_generator,
    )

    result = generator.run(agreement)

    assert result.lines == [mock_journal_line, mock_discount_line, mock_pls_line]
    mock_invoice_generator.run.assert_called_once()
    mock_generator_instance.generate.assert_called_once()
    mock_discounts_instance.process.assert_called_once()
    mock_pls_instance.process.assert_called_once()
    call_args = mock_generator_instance.generate.call_args
    assert call_args[0][0] == "ACC-1"
    assert call_args[0][1] == mock_account_usage
    assert isinstance(call_args[0][2], JournalDetails)


def test_run_without_pls(
    mocker,
    mock_context,
    mock_aws_client,
    mock_get_responsibility_transfer_id,
    mock_line_generator_cls,
    mock_extra_discounts_manager_cls,
    mock_pls_charge_manager_cls,
):
    mocker.patch(f"{MODULE}.generate_billing_report_rows", return_value=[])
    agreement = _build_agreement(support_type="DeveloperSupport")
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_discounts_instance = mocker.MagicMock(spec=ExtraDiscountsManager)
    mock_discounts_instance.process.return_value = []
    mock_extra_discounts_manager_cls.return_value = mock_discounts_instance
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
    mock_pls_charge_manager_cls.assert_not_called()


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
    mocker.patch(f"{MODULE}.generate_billing_report_rows", return_value=[])
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
    mock_discounts_instance = mocker.MagicMock(spec=ExtraDiscountsManager)
    mock_discounts_instance.process.return_value = []
    mock_extra_discounts_manager_cls.return_value = mock_discounts_instance
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
    mocker.patch(f"{MODULE}.generate_billing_report_rows", return_value=[])
    agreement = _build_agreement(support_type="PartnerLedSupport")
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = []
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_discounts_instance = mocker.MagicMock(spec=ExtraDiscountsManager)
    mock_discounts_instance.process.return_value = []
    mock_extra_discounts_manager_cls.return_value = mock_discounts_instance
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
    mock_pls_charge_manager_cls.assert_not_called()


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
    mocker.patch(f"{MODULE}.generate_billing_report_rows", return_value=[])
    agreement = _build_agreement(support_type="ResoldSupport")
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_pls_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_discounts_instance = mocker.MagicMock(spec=ExtraDiscountsManager)
    mock_discounts_instance.process.return_value = []
    mock_extra_discounts_manager_cls.return_value = mock_discounts_instance
    mock_pls_instance = mocker.MagicMock(spec=PlSChargeManager)
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
