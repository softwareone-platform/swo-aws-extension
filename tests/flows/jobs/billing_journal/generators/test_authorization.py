import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE, BillingJournalUsageSourceEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.cost_usage_report import (
    CostUsageReportGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AgreementJournalResult,
    AuthorizationJournalResult,
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
def mock_cur_usage_generator_cls(mocker):
    mock = mocker.patch(f"{MODULE}.CostUsageReportGenerator", autospec=True)
    mock.return_value = mocker.MagicMock(spec=CostUsageReportGenerator)
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
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = AgreementJournalResult(lines=[mock_journal_line], report=report)
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result.reports_by_agreement == {"AGR-1": report}


def test_build_usage_generator_uses_cur_prefix_with_billing_view(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_aws_client_cls,
    mock_cur_usage_generator_cls,
):
    mock_context.usage_source = BillingJournalUsageSourceEnum.COST_USAGE_REPORT
    authorization = {
        "id": "AUTH-1",
        "currency": "USD",
        "externalIds": {"operations": "651706759263"},
    }
    mock_get_agreements.return_value = [{"id": "AGR-1", "externalIds": {"vendor": "651706759263"}}]
    mock_agreement_generator = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agreement_generator.run.return_value = AgreementJournalResult()
    mock_agreement_generator_cls.return_value = mock_agreement_generator
    mock_aws_client = mock_aws_client_cls.return_value
    generator = AuthorizationJournalGenerator(mock_context)

    generator.run(authorization)

    mock_cur_usage_generator_cls.assert_called_once_with(mock_aws_client)
    mock_aws_client.get_billing_views_by_account_id.assert_not_called()


def test_build_usage_generator_falls_back_to_base_cur_prefix(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    mock_aws_client_cls,
    mock_cur_usage_generator_cls,
):
    mock_context.usage_source = BillingJournalUsageSourceEnum.COST_USAGE_REPORT
    authorization = {
        "id": "AUTH-1",
        "currency": "USD",
        "externalIds": {"operations": "651706759263"},
    }
    mock_get_agreements.return_value = [{"id": "AGR-1", "externalIds": {"vendor": "225989344502"}}]
    mock_agreement_generator = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agreement_generator.run.return_value = AgreementJournalResult()
    mock_agreement_generator_cls.return_value = mock_agreement_generator
    mock_aws_client = mock_aws_client_cls.return_value
    generator = AuthorizationJournalGenerator(mock_context)

    generator.run(authorization)

    mock_cur_usage_generator_cls.assert_called_once_with(mock_aws_client)
    mock_aws_client.get_billing_views_by_account_id.assert_not_called()
