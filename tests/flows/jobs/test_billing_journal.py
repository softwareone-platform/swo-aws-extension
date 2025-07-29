import pytest

from swo_aws_extension.constants import (
    ItemSkusEnum,
    SubscriptionStatusEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator import (
    BillingJournalGenerator,
    GenerateItemJournalLines,
    GenerateJournalLines,
    GenerateOtherServicesJournalLines,
    GenerateSupportEnterpriseJournalLines,
    GenerateSupportJournalLines,
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
    subscriptions = subscriptions_factory(
        vendor_id="1234-5678",
        status=SubscriptionStatusEnum.TERMINATED.value,
    )
    agreement_data = agreement_factory(vendor_id="123456789012", subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    mocker.patch.object(
        generator,
        "_get_organization_invoices",
        side_effect=Exception("Test exception"),
        autospec=True,
    )
    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.send_error", autospec=True
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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
    linked_account = "1234-1234-1234"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE.value,
    )
    mpa_account = "123456789012"
    agreement_data = agreement_factory(vendor_id=mpa_account, subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
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
    mocker.patch("swo_aws_extension.flows.jobs.billing_journal.send_error", autospec=True)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    result = generator._generate_agreement_journal_lines(agreement_data)
    assert result == []


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
        "swo_aws_extension.flows.jobs.billing_journal.AWSClient",
        side_effect=AWSError("error"),
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    mocker.patch.object(generator.mpt_api_client.billing.journal, "upload")
    generator.generate_billing_journals()
    awsclient_patch.assert_called_once()


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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )

    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.send_error", autospec=True
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


def test_generate_item_journal_lines_process_not_implemented():
    base = GenerateItemJournalLines("metric", 1, 0)
    with pytest.raises(NotImplementedError):
        base.process("account_id", "item_external_id", {}, {}, {})


def test_generate_marketplace_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateJournalLines(
        UsageMetricTypeEnum.MARKETPLACE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args(external_id)

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Marketplace service",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_usage_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_USAGE.value
    args = mock_journal_args(external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Usage service",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_usage_incentivate_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=12
    )
    external_id = ItemSkusEnum.AWS_USAGE_INCENTIVATE.value
    args = mock_journal_args(external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Usage service incentivate",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_other_services_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateOtherServicesJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_OTHER_SERVICES.value
    args = mock_journal_args(external_id)

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Other AWS services",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_support_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateSupportJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_SUPPORT.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {"AWS Support (Business)": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.REFUND.value] = {"refund": 7}

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="AWS Support (Business)",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_support_enterprise_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSupportEnterpriseJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=35
    )
    item_external_id = ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value
    args = mock_journal_args(item_external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {"AWS Support (Enterprise)": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.REFUND.value] = {"refund": 35}

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="AWS Support (Enterprise)",
        item_external_id=item_external_id,
    )
    assert result == [journal_line]


def test_generate_recurring_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateJournalLines(
        UsageMetricTypeEnum.RECURRING.value, billing_discount_tolerance_rate=1, discount=7
    )
    item_external_id = ItemSkusEnum.UPFRONT.value
    args = mock_journal_args(item_external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Upfront service",
        item_external_id=item_external_id,
    )
    assert result == [journal_line]


def test_generate_recurring_incentivate_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateJournalLines(
        UsageMetricTypeEnum.RECURRING.value, billing_discount_tolerance_rate=1, discount=12
    )
    item_external_id = ItemSkusEnum.UPFRONT_INCENTIVATE.value
    args = mock_journal_args(item_external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Upfront service incentivate",
        item_external_id=item_external_id,
    )
    assert result == [journal_line]


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
        "swo_aws_extension.flows.jobs.billing_journal.get_authorizations",
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
    mocker.patch.object(generator, "_get_account_metrics", return_value={}, autospec=True)
    mocker.patch.object(generator, "_get_organization_invoices", return_value={}, autospec=True)
    mocker.patch.object(generator, "_get_organization_reports", return_value={}, autospec=True)

    linked_account = "1234-1234-1234"
    subscriptions = subscriptions_factory(
        vendor_id=linked_account,
        status=SubscriptionStatusEnum.ACTIVE.value,
        lines=lines_factory(external_vendor_id="invalid", name="invalid item"),
    )
    mpa_account = "123456789012"
    agreement_data = agreement_factory(vendor_id=mpa_account, subscriptions=subscriptions)
    mocker.patch(
        "swo_aws_extension.flows.jobs.billing_journal.get_agreements_by_query",
        return_value=[agreement_data],
        autospec=True,
    )
    _, _ = aws_client_factory(config, "aws_mpa", "aws_role")

    upload_mock = mocker.patch.object(
        generator.mpt_api_client.billing.journal, "upload", autospec=True
    )

    generator.generate_billing_journals()
    upload_mock.assert_not_called()
