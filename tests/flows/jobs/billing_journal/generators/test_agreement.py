from typing import Any

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    BaseOrganizationUsageGenerator,
)
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

_PM_ACCOUNT_ID = "pm-account-123"
_MPA_ACCOUNT_ID = "MPA"


@pytest.fixture
def mock_aws_client(mocker: Any) -> Any:
    return mocker.MagicMock(spec=AWSClient)


@pytest.fixture
def mock_line_generator_cls(mocker: Any) -> Any:
    return mocker.patch(f"{MODULE}.JournalLineGenerator", autospec=True)


@pytest.fixture
def mock_invoice_generator_cls(mocker: Any) -> Any:
    return mocker.patch(f"{MODULE}.InvoiceGenerator", autospec=True)


@pytest.fixture
def mock_extra_discounts_manager_cls(mocker: Any) -> Any:
    return mocker.patch(f"{MODULE}.ExtraDiscountsManager", autospec=True)


@pytest.fixture
def mock_pls_charge_manager_cls(mocker: Any) -> Any:
    return mocker.patch(f"{MODULE}.PlSChargeManager", autospec=True)


def _agreement(ordering_parameters: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "id": "AGR-1",
        "externalIds": {"vendor": _MPA_ACCOUNT_ID},
        "parameters": {
            "ordering": ordering_parameters or [],
            "fulfillment": [],
        },
    }


def test_run_uses_cost_usage_report_when_no_usage_generator_is_injected(
    mocker: Any,
    mock_context: Any,
    mock_aws_client: Any,
    mock_line_generator_cls: Any,
    mock_invoice_generator_cls: Any,
    mock_extra_discounts_manager_cls: Any,
    mock_pls_charge_manager_cls: Any,
) -> None:
    agreement = _agreement()
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_extra_discounts_manager_cls.return_value.process.return_value = []
    mock_pls_charge_manager_cls.return_value.process.return_value = []
    mock_account_usage = mocker.MagicMock(spec=AccountUsage)
    mock_cost_usage_cls = mocker.patch(f"{MODULE}.CostUsageReportGenerator", autospec=True)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mock_account_usage}
    mock_cost_usage_cls.return_value.run.return_value = mock_usage_result
    organization_invoice = OrganizationInvoice()
    mock_invoice_generator_cls.return_value.run.return_value = OrganizationInvoiceResult(
        invoice=organization_invoice,
    )
    generator = AgreementJournalGenerator("USD", mock_context, mock_aws_client, _PM_ACCOUNT_ID)

    result = generator.run(agreement)

    assert result.lines == [mock_journal_line]
    assert result.report == mock_usage_result.reports
    mock_invoice_generator_cls.assert_called_once_with(mock_aws_client)
    mock_invoice_generator_cls.return_value.run.assert_called_once_with(
        _MPA_ACCOUNT_ID,
        mock_context.billing_period,
        "USD",
    )
    mock_cost_usage_cls.assert_called_once_with(
        mock_aws_client,
        S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=_PM_ACCOUNT_ID),
        S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=_MPA_ACCOUNT_ID),
    )
    mock_cost_usage_cls.return_value.run.assert_called_once_with(
        "USD",
        _MPA_ACCOUNT_ID,
        mock_context.billing_period,
        organization_invoice=organization_invoice,
    )
    mock_pls_charge_manager_cls.assert_not_called()


def test_run_uses_injected_usage_generator(
    mocker: Any,
    mock_context: Any,
    mock_aws_client: Any,
    mock_line_generator_cls: Any,
    mock_invoice_generator_cls: Any,
    mock_extra_discounts_manager_cls: Any,
    mock_pls_charge_manager_cls: Any,
) -> None:
    agreement = _agreement()
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_extra_discounts_manager_cls.return_value.process.return_value = []
    mock_pls_charge_manager_cls.return_value.process.return_value = []
    mock_account_usage = mocker.MagicMock(spec=AccountUsage)
    mock_cost_usage_cls = mocker.patch(f"{MODULE}.CostUsageReportGenerator", autospec=True)
    mock_usage_generator = mocker.MagicMock(spec=BaseOrganizationUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mock_account_usage}
    mock_usage_generator.run.return_value = mock_usage_result
    organization_invoice = OrganizationInvoice()
    mock_invoice_generator_cls.return_value.run.return_value = OrganizationInvoiceResult(
        invoice=organization_invoice,
    )
    generator = AgreementJournalGenerator(
        "USD",
        mock_context,
        mock_aws_client,
        _PM_ACCOUNT_ID,
        usage_generator=mock_usage_generator,
    )

    result = generator.run(agreement)

    assert result.lines == [mock_journal_line]
    assert result.report == mock_usage_result.reports
    mock_cost_usage_cls.assert_not_called()
    mock_usage_generator.run.assert_called_once_with(
        "USD",
        _MPA_ACCOUNT_ID,
        mock_context.billing_period,
        organization_invoice=organization_invoice,
    )
    mock_pls_charge_manager_cls.assert_not_called()


def test_run_adds_discount_and_pls_lines_for_resold_support(
    mocker: Any,
    mock_context: Any,
    mock_aws_client: Any,
    mock_line_generator_cls: Any,
    mock_invoice_generator_cls: Any,
    mock_extra_discounts_manager_cls: Any,
    mock_pls_charge_manager_cls: Any,
) -> None:
    agreement = _agreement(
        ordering_parameters=[{"externalId": "supportType", "value": "ResoldSupport"}]
    )
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_discount_line = mocker.MagicMock(spec=JournalLine)
    mock_pls_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_extra_discounts_manager_cls.return_value.process.return_value = [mock_discount_line]
    mock_pls_charge_manager_cls.return_value.process.return_value = [mock_pls_line]
    mock_account_usage = mocker.MagicMock(spec=AccountUsage)
    mock_cost_usage_cls = mocker.patch(f"{MODULE}.CostUsageReportGenerator", autospec=True)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mock_account_usage}
    mock_cost_usage_cls.return_value.run.return_value = mock_usage_result
    organization_invoice = OrganizationInvoice()
    mock_invoice_generator_cls.return_value.run.return_value = OrganizationInvoiceResult(
        invoice=organization_invoice,
    )
    generator = AgreementJournalGenerator("USD", mock_context, mock_aws_client, _PM_ACCOUNT_ID)

    result = generator.run(agreement)

    assert result.lines == [mock_journal_line, mock_discount_line, mock_pls_line]
    assert result.report == mock_usage_result.reports
    mock_line_generator_cls.assert_called_once_with(is_pls=True)
    mock_pls_charge_manager_cls.assert_called_once_with()


def test_run_returns_empty_when_no_mpa_account(
    mock_context: Any,
    mock_aws_client: Any,
    mock_line_generator_cls: Any,
    mock_invoice_generator_cls: Any,
    mock_extra_discounts_manager_cls: Any,
    mock_pls_charge_manager_cls: Any,
    mocker: Any,
) -> None:
    agreement = {
        "id": "AGR-1",
        "externalIds": {},
        "parameters": {"ordering": [], "fulfillment": []},
    }
    mock_cost_usage_cls = mocker.patch(f"{MODULE}.CostUsageReportGenerator", autospec=True)
    generator = AgreementJournalGenerator("USD", mock_context, mock_aws_client, _PM_ACCOUNT_ID)

    result = generator.run(agreement)

    assert result.lines == []
    assert result.report is None
    mock_line_generator_cls.assert_not_called()
    mock_invoice_generator_cls.assert_not_called()
    mock_cost_usage_cls.assert_not_called()
    mock_extra_discounts_manager_cls.assert_not_called()
    mock_pls_charge_manager_cls.assert_not_called()


def test_run_journal_line_details(
    mocker: Any,
    mock_context: Any,
    mock_aws_client: Any,
    mock_line_generator_cls: Any,
    mock_invoice_generator_cls: Any,
    mock_extra_discounts_manager_cls: Any,
    mock_pls_charge_manager_cls: Any,
) -> None:
    agreement = _agreement()
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = []
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_extra_discounts_manager_cls.return_value.process.return_value = []
    mock_pls_charge_manager_cls.return_value.process.return_value = []
    mock_account_usage = mocker.MagicMock(spec=AccountUsage)
    mock_cost_usage_cls = mocker.patch(f"{MODULE}.CostUsageReportGenerator", autospec=True)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = OrganizationReport()
    mock_usage_result.usage_by_account = {"ACC-1": mock_account_usage}
    mock_cost_usage_cls.return_value.run.return_value = mock_usage_result
    organization_invoice = OrganizationInvoice()
    mock_invoice_generator_cls.return_value.run.return_value = OrganizationInvoiceResult(
        invoice=organization_invoice,
    )
    generator = AgreementJournalGenerator("USD", mock_context, mock_aws_client, _PM_ACCOUNT_ID)

    result = generator.run(agreement)

    assert result.lines == []
    generate_args = mock_generator_instance.generate.call_args.args
    assert generate_args[0] == "ACC-1"
    assert generate_args[1] == mock_account_usage
    assert isinstance(generate_args[2], JournalDetails)
    assert generate_args[3] == organization_invoice
