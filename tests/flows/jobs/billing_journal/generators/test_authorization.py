import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AgreementJournalResult,
    AuthorizationJournalResult,
    BillingReportRow,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationReport

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.authorization"


@pytest.fixture
def authorization():
    return {"id": "AUTH-1", "currency": "USD", "externalIds": {"operations": "MPA-123"}}


@pytest.fixture
def mock_get_agreements(mocker):
    return mocker.patch(f"{MODULE}.get_agreements_by_query", autospec=True)


@pytest.fixture
def mock_agreement_generator_cls(mocker):
    return mocker.patch(f"{MODULE}.AgreementJournalGenerator", autospec=True)


@pytest.fixture
def mock_usage_generator_cls(mocker):
    mock = mocker.patch(f"{MODULE}.CostExplorerUsageGenerator", autospec=True)
    mock.return_value = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    return mock


@pytest.fixture
def mock_invoice_generator_cls(mocker):
    mock = mocker.patch(f"{MODULE}.InvoiceGenerator", autospec=True)
    mock.return_value = mocker.MagicMock(spec=InvoiceGenerator)
    return mock


@pytest.fixture
def mock_aws_client_cls(mocker):
    mock = mocker.patch(f"{MODULE}.AWSClient", autospec=True)
    mock.return_value = mocker.MagicMock(spec=AWSClient)
    return mock


@pytest.fixture
def mock_generate_billing_report_rows(mocker):
    return mocker.patch(f"{MODULE}.generate_billing_report_rows", autospec=True)


def test_no_agreements_returns_empty_list(
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_usage_generator_cls,
    mock_invoice_generator_cls,
    mock_aws_client_cls,
    authorization,
):
    mock_get_agreements.return_value = []
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result == AuthorizationJournalResult()
    mock_agreement_generator_cls.assert_not_called()


def test_processes_agreements(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_usage_generator_cls,
    mock_invoice_generator_cls,
    mock_aws_client_cls,
    authorization,
):
    mock_get_agreements.return_value = [{"id": "AGR-1"}, {"id": "AGR-2"}]
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = AgreementJournalResult(lines=[mock_journal_line])
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert mock_agr_gen.run.call_count == 2
    assert result.lines == [mock_journal_line, mock_journal_line]


def test_exception_sends_error(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_usage_generator_cls,
    mock_invoice_generator_cls,
    mock_aws_client_cls,
    authorization,
):
    mock_get_agreements.return_value = [{"id": "AGR-1"}]
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.side_effect = Exception("Test Error")
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result == AuthorizationJournalResult()
    expected_message = "Failed to generate billing journal for AGR-1: Test Error"
    mock_context.notifier.send_error.assert_called_once_with(
        BILLING_JOURNAL_ERROR_TITLE, expected_message
    )


def test_includes_report_in_result(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_usage_generator_cls,
    mock_invoice_generator_cls,
    mock_aws_client_cls,
    authorization,
):
    report = OrganizationReport(organization_data={"usage": [{"key": "val"}]})
    mock_get_agreements.return_value = [{"id": "AGR-1"}]
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_row = mocker.MagicMock(spec=BillingReportRow)
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = AgreementJournalResult(
        lines=[mock_journal_line], report=report, billing_report_rows=[mock_row]
    )
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result.reports_by_agreement == {"AGR-1": report}
    assert result.billing_report_rows == [mock_row]


def test_pma_usage_included_in_report_rows(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_usage_generator_cls,
    mock_invoice_generator_cls,
    mock_aws_client_cls,
    mock_generate_billing_report_rows,
    authorization,
):
    mock_get_agreements.return_value = [{"id": "AGR-1"}]
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = AgreementJournalResult(
        lines=[], report=None, billing_report_rows=[]
    )
    mock_agreement_generator_cls.return_value = mock_agr_gen
    mock_invoice_gen = mock_invoice_generator_cls.return_value
    mock_usage_gen = mock_usage_generator_cls.return_value
    mock_pma_invoice_result = mocker.MagicMock()
    mock_pma_usage_result = mocker.MagicMock()
    mock_invoice_gen.run.return_value = mock_pma_invoice_result
    mock_usage_gen.run_for_pma.return_value = mock_pma_usage_result
    mock_row = mocker.MagicMock(spec=BillingReportRow)
    mock_generate_billing_report_rows.return_value = [mock_row]
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    mock_invoice_gen.run.assert_any_call("MPA-123", mock_context.billing_period, "USD")
    mock_usage_gen.run_for_pma.assert_called_once_with(
        "MPA-123",
        mock_context.billing_period,
        organization_invoice=mock_pma_invoice_result.invoice,
        granularity="MONTHLY",
    )
    mock_generate_billing_report_rows.assert_called_once()
    assert mock_row in result.billing_report_rows


def test_pma_usage_error_does_not_crash(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_usage_generator_cls,
    mock_invoice_generator_cls,
    mock_aws_client_cls,
    mock_generate_billing_report_rows,
    authorization,
):
    mock_get_agreements.return_value = [{"id": "AGR-1"}]
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = AgreementJournalResult(
        lines=[],
        report=None,
        billing_report_rows=[],
    )
    mock_agreement_generator_cls.return_value = mock_agr_gen
    mock_invoice_gen = mock_invoice_generator_cls.return_value
    mock_invoice_gen.run.side_effect = AWSError("PMA invoice fetch failed")
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result.billing_report_rows == []
    mock_generate_billing_report_rows.assert_not_called()
