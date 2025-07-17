import pytest

from swo_aws_extension.constants import SubscriptionStatusEnum
from swo_aws_extension.flows.jobs.billing_journal import BillingJournalGenerator
from swo_mpt_api.models.hints import Journal
from swo_rql import RQLQuery


@pytest.fixture
def journal_data():
    return Journal(
        name="Test Journal",
    )


def test_generate_billing_journals_no_authorizations(
    mocker, mpt_client, requests_mocker, mpt_error_factory
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"])
    mocker_get_authorizations = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=None,
    )

    generator.generate_billing_journals()
    mocker_get_authorizations.assert_called_once_with(
        mpt_client, RQLQuery(product__id__in=["prod1"])
    )


def test_generate_billing_journals_create_journal_empty_agreements(
    mocker, mpt_client, journal_data
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"])
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = []
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[],
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_authorization_with_no_agreements_create_new_journal(
    mocker, mpt_client
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"])
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[],
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_authorization_no_mpa_found(
    mocker, mpt_client, agreement_factory
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"])
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_factory()],
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_authorization_not_active_subscription(
    mocker, mpt_client, agreement_factory, subscriptions_factory
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"])
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    subscriptions = subscriptions_factory(
        vendor_id="1234-5678",
        status=SubscriptionStatusEnum.TERMINATED,
    )
    agreement = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement],
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_authorization_exception(
    mocker, mpt_client, agreement_factory, subscriptions_factory
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"])
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    subscriptions = subscriptions_factory(
        vendor_id="1234-5678",
        status=SubscriptionStatusEnum.ACTIVE,
    )
    agreement = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement],
    )
    mocker.patch.object(
        generator, "_generate_subscription_journal_lines", side_effect=Exception("Test exception")
    )
    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.send_error",
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_not_called()
    upload_mock.assert_not_called()
    send_error.assert_called_once()


def test_generate_billing_journals_authorization_upload_file(
    mocker, mpt_client, agreement_factory, subscriptions_factory
):
    generator = BillingJournalGenerator(mpt_client, {}, 2024, 5, ["prod1"], authorizations="AUTH-1")
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    subscriptions = subscriptions_factory(
        vendor_id="1234-5678",
        status=SubscriptionStatusEnum.ACTIVE,
    )
    agreement = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement],
    )
    mocker.patch.object(
        generator,
        "_generate_subscription_journal_lines",
        return_value={"description": "Test description"},
    )

    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_not_called()
    upload_mock.assert_called_once()
