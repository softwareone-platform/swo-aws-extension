from swo_aws_extension.constants import (
    ItemSkusEnum,
    SubscriptionStatusEnum,
    TransferTypesEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator import (
    BillingJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingException
from swo_aws_extension.flows.jobs.billing_journal.item_journal_line import (
    GenerateSupportEnterpriseJournalLines,
    get_journal_processors,
)
from swo_rql import RQLQuery


def test_generate_billing_journals_no_authorizations(
    mocker, mpt_client, requests_mocker, mpt_error_factory, config, aws_client_factory
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker_get_authorizations = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=None,
        autospec=True,
    )

    generator.generate_billing_journals()
    mocker_get_authorizations.assert_called_once_with(
        mpt_client, RQLQuery(product__id__in=["prod1"])
    )


def test_generate_billing_journals_create_journal_empty_agreements(
    mocker, mpt_client, config, aws_client_factory
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = []
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[],
        autospec=True,
    )
    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload", autospec=True)
    generator.generate_billing_journals()
    mock_create.assert_called_once()


def test_generate_billing_journals_authorization_with_no_agreements_create_new_journal(
    mocker, mpt_client, config, aws_client_factory
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[],
        autospec=True,
    )
    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload", autospec=True)
    generator.generate_billing_journals()
    mock_create.assert_called_once()


def test_generate_billing_journals_authorization_no_mpa_found(
    mocker, mpt_client, agreement_factory, config, aws_client_factory
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_factory()],
        autospec=True,
    )
    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )
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
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_add_attachments",
        return_value=None,
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    subscriptions = subscriptions_factory(
        vendor_id="1234-5678",
        status=SubscriptionStatusEnum.TERMINATED.value,
    )
    agreement_data = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")
    aws_mock.list_invoice_summaries.return_value = {
        "InvoiceSummaries": [data_aws_invoice_summary_factory()],
    }
    aws_mock.get_cost_and_usage.side_effect = [
        mock_marketplace_report_factory(),
        mock_invoice_by_service_report_factory(),
    ]

    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_authorization_exception(
    mocker, mpt_client, agreement_factory, subscriptions_factory, config, aws_client_factory
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )

    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )

    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    subscriptions = subscriptions_factory(
        vendor_id="1234-5678",
        status=SubscriptionStatusEnum.ACTIVE.value,
    )
    agreement_data = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_get_marketplace_usage_report",
        side_effect=Exception("Test exception"),
        autospec=True,
    )
    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_error",
        autospec=True,
    )
    aws_client_factory(config, "aws_mpa", "aws_role")

    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload", autospec=True)
    generator.generate_billing_journals()

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
    mock_report_type_and_usage_report_group_factory,
    mock_report_type_and_usage_report_factory,
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
        authorizations=["AUTH-1"],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    attach_mock = mocker.patch(
        "swo_mpt_api.billing.journal_client.AttachmentsClient.upload", autospec=True
    )
    linked_account = "1234-1234-1234"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE.value,
    )
    mpa_account = "123456789012"
    agreement_data = agreement_factory(vendor_id=mpa_account, subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    send_success = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_success",
        autospec=True,
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")

    groups = mock_marketplace_report_group_factory(account_id=linked_account)
    groups.extend(mock_marketplace_report_group_factory(account_id=mpa_account))

    aws_mock.get_cost_and_usage.side_effect = [
        mock_marketplace_report_factory(groups=groups),
        mock_invoice_by_service_report_factory(),
        mock_report_type_and_usage_report_factory(),
        mock_invoice_by_service_report_factory(),
        mock_report_type_and_usage_report_factory(),
    ]
    aws_mock.list_invoice_summaries.side_effect = [
        {
            "InvoiceSummaries": [
                data_aws_invoice_summary_factory(account_id=linked_account),
                data_aws_invoice_summary_factory(account_id=mpa_account),
            ],
        },
    ]
    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )

    generator.generate_billing_journals()
    upload_mock.assert_called_once()
    send_success.assert_called_once()
    attach_mock.assert_called_once()


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
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=subscriptions_factory(
            vendor_id="1234-1234-1234", status=SubscriptionStatusEnum.ACTIVE.value
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
    mocker.patch.object(
        generator, "_generate_subscription_journal_lines", side_effect=Exception("sub error")
    )
    mocker.patch.object(generator, "_generate_mpa_journal_lines", return_value=[], autospec=True)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_error",
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_add_attachments",
        return_value=None,
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    generator._generate_agreement_journal_lines(agreement_data, "JOURNAL-1")
    assert generator.journal_file_lines == []


def test_generate_agreement_journal_lines_aws_client_error(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
):
    from swo_aws_extension.aws.errors import AWSError

    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=subscriptions_factory(
            vendor_id="1234-1234-1234", status=SubscriptionStatusEnum.ACTIVE.value
        ),
    )
    awsclient_patch = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.AWSClient",
        side_effect=AWSError("error"),
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_error",
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    awsclient_patch.assert_called_once()
    send_error.assert_called_once()


def test_generate_subscription_journal_lines_exception(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    subscription = subscriptions_factory(
        vendor_id="1234-1234-1234", status=SubscriptionStatusEnum.ACTIVE.value
    )[0]
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=[subscription],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(generator.mpt_api_client.billing.journal, "query")
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )

    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_error",
        autospec=True,
    )
    get_account_metrics_patch = mocker.patch.object(
        generator,
        "_generate_authorization_journal",
        side_effect=Exception("metrics error"),
        autospec=True,
    )
    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )
    generator.generate_billing_journals()
    send_error.assert_called_once()
    get_account_metrics_patch.assert_called_once()
    mock_create.assert_not_called()
    upload_mock.assert_not_called()


def test_generate_billing_journals_item_not_supported(
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
    mock_report_type_and_usage_report_group_factory,
    mock_report_type_and_usage_report_factory,
    lines_factory,
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
        authorizations=["AUTH-1"],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_add_attachments",
        return_value=None,
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    mocker.patch.object(generator, "_get_account_metrics", return_value={}, autospec=True)
    mocker.patch.object(generator, "_get_organization_invoices", return_value={}, autospec=True)
    mocker.patch.object(generator, "_get_marketplace_usage_report", return_value={}, autospec=True)

    linked_account = "1234-1234-1234"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE.value,
        lines=lines_factory(external_vendor_id="invalid", name="invalid item"),
    )
    mpa_account = "123456789012"
    agreement_data = agreement_factory(vendor_id=mpa_account, subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    _, _ = aws_client_factory(config, "aws_mpa", "aws_role")

    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )

    generator.generate_billing_journals()
    upload_mock.assert_not_called()


def test_process_item_journal_line_error(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
    mock_journal_line_factory,
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2025,
        1,
        ["prod1"],
        billing_journal_processor={
            ItemSkusEnum.AWS_SUPPORT.value: GenerateSupportEnterpriseJournalLines("metric", 1, 0)
        },
        authorizations=["AUTH-1"],
    )
    mocker.patch.object(
        generator,
        "_add_attachments",
        return_value=None,
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    payload = {
        "service_name": "TestService",
        "amount": 100.0,
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.item_journal_line.GenerateSupportEnterpriseJournalLines.process",
        side_effect=AWSBillingException("Test error", payload=payload),
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    linked_account = "1234567890"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE.value,
    )
    mpa_account = "mpa_id"
    agreement_data = agreement_factory(vendor_id=mpa_account, subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_error",
        autospec=True,
    )
    mocker.patch("swo_mpt_api.billing.journal_client.AttachmentsClient.upload", autospec=True)

    _, _ = aws_client_factory(config, "aws_mpa", "aws_role")
    mocker.patch.object(generator, "_get_account_metrics", return_value={}, autospec=True)
    mocker.patch.object(generator, "_get_organization_invoices", return_value={}, autospec=True)
    mocker.patch.object(generator, "_get_marketplace_usage_report", return_value={}, autospec=True)

    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )

    generator.generate_billing_journals()
    upload_mock.assert_called_once()
    journal_line = mock_journal_line_factory(
        service_name="TestService",
        item_external_id=ItemSkusEnum.AWS_SUPPORT.value,
        error="Test error",
        invoice_id=None,
        invoice_entity="",
    )

    assert generator.journal_file_lines == [journal_line, journal_line]
    send_error.assert_called_once()


def test_generate_billing_journals_authorization_subscription_without_vendor_external(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
    data_aws_invoice_summary_factory,
    mock_marketplace_report_factory,
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_add_attachments",
        return_value=None,
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mock_create = mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    subscriptions = subscriptions_factory(vendor_id="")
    agreement_data = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")
    aws_mock.list_invoice_summaries.return_value = {
        "InvoiceSummaries": [data_aws_invoice_summary_factory()],
    }
    mpa_account = "123456789012"

    aws_mock.list_invoice_summaries.side_effect = [
        {
            "InvoiceSummaries": [
                data_aws_invoice_summary_factory(),
                data_aws_invoice_summary_factory(),
                data_aws_invoice_summary_factory(account_id=mpa_account),
            ],
        },
    ]
    aws_mock.get_cost_and_usage.side_effect = [mock_marketplace_report_factory()]

    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )
    generator.generate_billing_journals()
    mock_create.assert_called_once()
    upload_mock.assert_not_called()


def test_generate_billing_journals_skip_mpa_usage_split_billing(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
    data_aws_invoice_summary_factory,
    mock_marketplace_report_factory,
    order_parameters_factory,
):
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2024,
        5,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_add_attachments",
        return_value=None,
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Completed"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    subscriptions = subscriptions_factory(vendor_id="")
    ordering_parameters = order_parameters_factory(transfer_type=TransferTypesEnum.SPLIT_BILLING)
    agreement_data = agreement_factory(
        vendor_id="123456789012",
        subscriptions=subscriptions,
        ordering_parameters=ordering_parameters,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")
    aws_mock.list_invoice_summaries.return_value = {
        "InvoiceSummaries": [data_aws_invoice_summary_factory()],
    }
    aws_mock.list_invoice_summaries.side_effect = [
        {
            "InvoiceSummaries": [
                data_aws_invoice_summary_factory(),
            ],
        },
    ]
    aws_mock.get_cost_and_usage.side_effect = [mock_marketplace_report_factory()]

    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload", autospec=True)
    generator.generate_billing_journals()
    aws_mock.list_invoice_summaries.assert_called_once()


def test_process_item_invalid_service_provider_discount(
    mocker,
    mpt_client,
    agreement_factory,
    subscriptions_factory,
    config,
    aws_client_factory,
    mock_journal_line_factory,
    mock_marketplace_report_group_factory,
    mock_marketplace_report_factory,
    mock_invoice_by_service_report_factory,
    mock_report_type_and_usage_report_factory,
    data_aws_invoice_summary_factory,
    mock_report_type_and_usage_report_group_factory,
):
    service_name = "AWS invalid discount service name"
    generator = BillingJournalGenerator(
        mpt_client,
        config,
        2025,
        1,
        ["prod1"],
        billing_journal_processor=get_journal_processors(config),
        authorizations=["AUTH-1"],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_authorizations",
        return_value=[{"id": "AUTH-1"}],
        autospec=True,
    )
    mock_journal_query = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "query", autospec=True
    )
    mock_journal_query.return_value.all.return_value = [{"id": "JOURNAL-1", "status": "Draft"}]
    mocker.patch.object(
        generator.mpt_api_client.billing.journal,
        "create",
        return_value={"id": "JOURNAL-1"},
        autospec=True,
    )
    linked_account = "1234567890"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE.value,
    )
    agreement_data = agreement_factory(vendor_id="mpa_id", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator.send_error",
        autospec=True,
    )
    mocker.patch("swo_mpt_api.billing.journal_client.AttachmentsClient.upload", autospec=True)

    _, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")

    report_type_groups = mock_report_type_and_usage_report_group_factory(
        record_type=UsageMetricTypeEnum.USAGE,
        service_name=service_name,
        service_amount="100",
        provider_discount_amount="3",
    )
    report_type_groups.extend(
        mock_report_type_and_usage_report_group_factory(
            record_type=UsageMetricTypeEnum.REFUND,
            service_name="refund",
            service_amount="-100",
            provider_discount_amount="0",
        )
    )
    report_type_groups.extend(
        mock_report_type_and_usage_report_group_factory(
            record_type=UsageMetricTypeEnum.USAGE,
            service_name="Tax",
            service_amount="-5",
            provider_discount_amount="0",
        )
    )

    aws_mock.get_cost_and_usage.side_effect = [
        mock_marketplace_report_factory(),
        mock_invoice_by_service_report_factory(),
        mock_report_type_and_usage_report_factory(report_type_groups),
        mock_invoice_by_service_report_factory(),
        mock_report_type_and_usage_report_factory(groups=[]),
    ]
    aws_mock.list_invoice_summaries.side_effect = [
        {
            "InvoiceSummaries": [
                data_aws_invoice_summary_factory(account_id=linked_account),
                data_aws_invoice_summary_factory(account_id="mpa_id"),
            ],
        },
    ]

    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload", autospec=True)

    generator.generate_billing_journals()
    error_msg = (
        f"{linked_account} - Service {service_name} with amount 3.0 and discount 100.0 did "
        f"not match any subscription item."
    )
    journal_line = mock_journal_line_factory(
        service_name="AWS service name",
        item_external_id=ItemSkusEnum.AWS_USAGE.value,
        invoice_id="EUINGB25-2163550",
        invoice_entity="Amazon Web Services EMEA SARL",
    )
    journal_line_invalid = mock_journal_line_factory(
        service_name=service_name,
        item_external_id="Item not found",
        invoice_id=None,
        invoice_entity="",
        price=3.0,
        error=error_msg,
    )

    assert generator.journal_file_lines == [journal_line_invalid, journal_line]
