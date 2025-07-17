from swo_aws_extension.constants import SubscriptionStatusEnum
from swo_aws_extension.flows.jobs.billing_journal import BillingJournalGenerator
from swo_rql import RQLQuery


def test_generate_billing_journals_no_authorizations(
    mocker, mpt_client, requests_mocker, mpt_error_factory, config, aws_client_factory
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
    mocker_get_authorizations = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=None,
    )

    generator.generate_billing_journals()
    mocker_get_authorizations.assert_called_once_with(
        mpt_client, RQLQuery(product__id__in=["prod1"])
    )


def test_generate_billing_journals_create_journal_empty_agreements(
    mocker, mpt_client, config, aws_client_factory
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
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
    mocker, mpt_client, config, aws_client_factory
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
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
    mocker, mpt_client, agreement_factory, config, aws_client_factory
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
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
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
    data_aws_invoice_summary_factory,
    mock_invoice_by_service_report_factory,
    mock_marketplace_report_factory,
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
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
    agreement_data = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")
    aws_mock.list_invoice_summaries.return_value = {
        "InvoiceSummaries": [data_aws_invoice_summary_factory()],
    }
    aws_mock.get_cost_and_usage.side_effect = [
        mock_marketplace_report_factory(),
        mock_invoice_by_service_report_factory(),
    ]

    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_authorization_exception(
    mocker, mpt_client, agreement_factory, subscriptions_factory, config, aws_client_factory
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
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
    agreement_data = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
    )
    mocker.patch.object(
        generator, "_get_organization_invoices", side_effect=Exception("Test exception")
    )
    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.send_error",
    )
    aws_client_factory(config, "aws_mpa", "aws_role")

    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    mock_create.assert_not_called()
    upload_mock.assert_not_called()
    send_error.assert_called_once()


def test_generate_billing_journals_authorization_upload_file(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    mock_marketplace_report_factory,
    data_aws_invoice_summary_factory,
    mock_invoice_by_service_report_factory,
    config,
    aws_client_factory,
    mock_marketplace_report_group_factory,
):
    generator = BillingJournalGenerator(
        mpt_client, config, 2024, 5, ["prod1"], authorizations=["AUTH-1"]
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    linked_account = "1234-1234-1234"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE,
    )
    mpa_account = "123456789012"
    agreement_data = agreement_factory(vendor_id=mpa_account, subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")

    groups = mock_marketplace_report_group_factory(account_id=linked_account)
    groups.extend(mock_marketplace_report_group_factory(account_id=mpa_account))

    aws_mock.get_cost_and_usage.side_effect = [
        mock_marketplace_report_factory(groups=groups),
        mock_invoice_by_service_report_factory(),
        mock_invoice_by_service_report_factory(),
    ]
    aws_mock.list_invoice_summaries.side_effect = [
        {
            "InvoiceSummaries": [
                data_aws_invoice_summary_factory(account_id=linked_account),
                data_aws_invoice_summary_factory(account_id=mpa_account),
            ],
        },
    ]
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")

    generator.generate_billing_journals()
    mock_create.assert_not_called()
    upload_mock.assert_called_once()


def test_generate_agreement_journal_lines_subscription_exception(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
    data_aws_invoice_summary_factory,
    mock_marketplace_report_factory,
    mock_invoice_by_service_report_factory,
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=subscriptions_factory(
            vendor_id="1234-1234-1234", status=SubscriptionStatusEnum.ACTIVE
        ),
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")
    aws_mock.list_invoice_summaries.return_value = {
        "InvoiceSummaries": [data_aws_invoice_summary_factory()],
    }
    aws_mock.get_cost_and_usage.side_effect = [
        mock_marketplace_report_factory(),
        mock_invoice_by_service_report_factory(),
    ]
    mock_sub_lines = mocker.patch.object(
        generator, "_generate_subscription_journal_lines", side_effect=Exception("sub error")
    )
    send_error = mocker.patch("swo_aws_extension.flows.jobs.billing_journal.send_error")
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
    )
    result = generator._generate_agreement_journal_lines(agreement_data)
    assert result == []
    send_error.assert_called_once()
    mock_sub_lines.assert_called_once()


def test_generate_agreement_journal_lines_aws_client_error(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
):
    from swo_aws_extension.aws.errors import AWSError

    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=subscriptions_factory(
            vendor_id="1234-1234-1234", status=SubscriptionStatusEnum.ACTIVE
        ),
    )
    awsclient_patch = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.AWSClient",
        side_effect=AWSError("error"),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    awsclient_patch.assert_called_once()
    mock_create.assert_not_called()
    upload_mock.assert_not_called()


def test_generate_subscription_journal_lines_exception(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
):
    generator = BillingJournalGenerator(mpt_client, config, 2024, 5, ["prod1"])
    subscription = subscriptions_factory(
        vendor_id="1234-1234-1234", status=SubscriptionStatusEnum.ACTIVE
    )[0]
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=[subscription],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "create", return_value={"id": "JOURNAL-1"}
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
    )

    send_error = mocker.patch("swo_aws_extension.flows.jobs.billing_journal.send_error")
    get_account_metrics_patch = mocker.patch.object(
        generator, "_generate_authorization_journal", side_effect=Exception("metrics error")
    )
    upload_mock = mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    send_error.assert_called_once()
    get_account_metrics_patch.assert_called_once()
    mock_create.assert_not_called()
    upload_mock.assert_not_called()
