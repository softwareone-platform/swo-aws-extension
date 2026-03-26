import pytest

from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.billing_journal_service import (
    BillingJournalService,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AuthorizationJournalResult,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationReport
from swo_aws_extension.swo.rql.query_builder import RQLQuery

MODULE = "swo_aws_extension.flows.jobs.billing_journal.billing_journal_service"


@pytest.fixture
def mock_get_authorizations(mocker):
    return mocker.patch(f"{MODULE}.get_authorizations", autospec=True)


@pytest.fixture
def mock_auth_generator_cls(mocker):
    return mocker.patch(f"{MODULE}.AuthorizationJournalGenerator", autospec=True)


def test_no_authorizations_skips_processing(
    mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    mock_get_authorizations.return_value = None
    service = BillingJournalService(mock_context)

    result = service.run()

    assert result is None
    mock_auth_generator_cls.return_value.run.assert_not_called()


def test_processes_authorizations(
    mocker, mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    authorization = {"id": "AUTH-1"}
    mock_get_authorizations.return_value = [authorization]
    mock_auth_gen = mocker.MagicMock(spec=AuthorizationJournalGenerator)
    mock_auth_gen.run.return_value = AuthorizationJournalResult()
    mock_auth_generator_cls.return_value = mock_auth_gen
    service = BillingJournalService(mock_context)

    service.run()  # act

    mock_auth_gen.run.assert_called_once_with(authorization)


def test_exception_sends_error(
    mocker, mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    mock_get_authorizations.return_value = [{"id": "AUTH-1"}]
    mock_auth_gen = mocker.MagicMock(spec=AuthorizationJournalGenerator)
    mock_auth_gen.run.side_effect = Exception("Test failure")
    mock_auth_generator_cls.return_value = mock_auth_gen
    service = BillingJournalService(mock_context)

    service.run()  # act

    expected_message = "Failed to generate billing journals for authorization AUTH-1"
    mock_context.notifier.send_error.assert_called_once_with(
        BILLING_JOURNAL_ERROR_TITLE, expected_message
    )


def test_builds_rql_query_with_authorizations(
    mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    mock_context.product_ids = ["PROD-1"]
    mock_context.authorizations = ["AUTH-1"]
    mock_get_authorizations.return_value = []
    service = BillingJournalService(mock_context)

    result = service.run()

    assert result is None
    expected_query = RQLQuery(id__in=["AUTH-1"]) & RQLQuery(product__id__in=["PROD-1"])
    mock_get_authorizations.assert_called_once_with(mock_context.mpt_client, expected_query)


def test_creates_new_journal_when_no_pending(
    mocker, mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    authorization = {"id": "AUTH-1"}
    mock_get_authorizations.return_value = [authorization]
    mock_auth_gen = mocker.MagicMock(spec=AuthorizationJournalGenerator)
    mock_line = mocker.MagicMock(spec=JournalLine)
    mock_auth_gen.run.return_value = AuthorizationJournalResult(lines=[mock_line])
    mock_auth_generator_cls.return_value = mock_auth_gen
    mock_journal_manager_cls = mocker.patch(f"{MODULE}.JournalManager", autospec=True)
    mock_journal_manager = mock_journal_manager_cls.return_value
    mock_journal_manager.get_pending_journal.return_value = None
    mock_journal_manager.create_new_journal.return_value = mocker.MagicMock(id="JRN-NEW")
    service = BillingJournalService(mock_context)

    service.run()  # act

    mock_journal_manager.create_new_journal.assert_called_once()


def test_uploads_journal_when_lines_generated(
    mocker, mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    authorization = {"id": "AUTH-1"}
    mock_get_authorizations.return_value = [authorization]
    mock_auth_gen = mocker.MagicMock(spec=AuthorizationJournalGenerator)
    mock_line = mocker.MagicMock(spec=JournalLine)
    mock_auth_gen.run.return_value = AuthorizationJournalResult(lines=[mock_line])
    mock_auth_generator_cls.return_value = mock_auth_gen
    mock_journal_manager_cls = mocker.patch(f"{MODULE}.JournalManager", autospec=True)
    mock_journal_manager = mock_journal_manager_cls.return_value
    mock_journal = mocker.MagicMock(id="JRN-1")
    mock_journal_manager.get_pending_journal.return_value = mock_journal
    service = BillingJournalService(mock_context)

    service.run()  # act

    mock_journal_manager.upload_journal.assert_called_once_with("JRN-1", [mock_line])
    mock_journal_manager.notify_success.assert_called_once_with("JRN-1", 1)


def test_builds_rql_query_without_authorizations(
    mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    mock_context.product_ids = ["PROD-1"]
    mock_context.authorizations = None
    mock_get_authorizations.return_value = []
    service = BillingJournalService(mock_context)

    result = service.run()

    assert result is None
    expected_query = RQLQuery(product__id__in=["PROD-1"])
    mock_get_authorizations.assert_called_once_with(mock_context.mpt_client, expected_query)


def test_uploads_attachments_when_reports_present(
    mocker, mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = False
    authorization = {"id": "AUTH-1"}
    mock_get_authorizations.return_value = [authorization]
    report = OrganizationReport(organization_data={"usage": [{"key": "val"}]})
    mock_auth_gen = mocker.MagicMock(spec=AuthorizationJournalGenerator)
    mock_line = mocker.MagicMock(spec=JournalLine)
    mock_auth_gen.run.return_value = AuthorizationJournalResult(
        lines=[mock_line],
        reports_by_agreement={"AGR-1": report},
    )
    mock_auth_generator_cls.return_value = mock_auth_gen
    mock_journal_manager_cls = mocker.patch(f"{MODULE}.JournalManager", autospec=True)
    mock_journal_manager = mock_journal_manager_cls.return_value
    mock_journal = mocker.MagicMock(id="JRN-1")
    mock_journal_manager.get_pending_journal.return_value = mock_journal
    service = BillingJournalService(mock_context)

    service.run()  # act

    mock_journal_manager.upload_attachments.assert_called_once_with("JRN-1", {"AGR-1": report})
    mock_journal_manager.notify_success.assert_called_once_with("JRN-1", 1)


def test_dry_run_skips_upload(
    mocker, mock_context, mock_get_authorizations, mock_auth_generator_cls
):
    mock_context.dry_run = True
    authorization = {"id": "AUTH-1"}
    mock_get_authorizations.return_value = [authorization]
    mock_auth_gen = mocker.MagicMock(spec=AuthorizationJournalGenerator)
    mock_line = mocker.MagicMock(spec=JournalLine)
    mock_line.to_jsonl.return_value = '{"test": 1}\n'
    report = OrganizationReport(organization_data={"usage": [{"key": "val"}]})
    mock_auth_gen.run.return_value = AuthorizationJournalResult(
        lines=[mock_line],
        reports_by_agreement={"AGR-1": report},
    )
    mock_auth_generator_cls.return_value = mock_auth_gen
    mock_journal_manager_cls = mocker.patch(f"{MODULE}.JournalManager", autospec=True)
    service = BillingJournalService(mock_context)

    service.run()  # act

    mock_journal_manager_cls.assert_not_called()
