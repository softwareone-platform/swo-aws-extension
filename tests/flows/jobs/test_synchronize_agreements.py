import botocore.exceptions
from freezegun import freeze_time

from swo_aws_extension.constants import (
    AWS_ITEMS_SKUS,
    SWO_EXTENSION_MANAGEMENT_ROLE,
)
from swo_aws_extension.flows.jobs.synchronize_agreements import (
    _synchronize_new_accounts,
    sync_agreement_subscriptions,
    synchronize_agreements,
)
from swo_aws_extension.parameters import FulfillmentParametersEnum


def test_synchronize_agreement_with_specific_ids(
    mocker, mpt_client, config, agreement_factory, aws_client_factory
):
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )
    aws_client, _ = aws_client_factory(config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE)
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.AWSClient",
        return_value=aws_client,
    )
    mock_sync = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.sync_agreement_subscriptions"
    )
    synchronize_agreements(mpt_client, config, ["AGR-123-456"], False, "PROD-123-456")
    mock_sync.assert_called_once_with(mpt_client, aws_client, mock_agreement, False)


def test_synchronize_agreement_without_ids(
    mocker, mpt_client, config, agreement_factory, aws_client_factory
):
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )
    aws_client, _ = aws_client_factory(config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE)
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.AWSClient",
        return_value=aws_client,
    )
    mock_sync = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.sync_agreement_subscriptions"
    )
    synchronize_agreements(mpt_client, config, None, False, "PROD-123-456")
    mock_sync.assert_called_once_with(mpt_client, aws_client, mock_agreement, False)


def test_synchronize_agreement_without_mpa(
    mocker, mpt_client, config, agreement_factory, aws_client_factory
):
    mock_agreement = agreement_factory(vendor_id="")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )
    aws_client, _ = aws_client_factory(config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE)
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.AWSClient",
        return_value=aws_client,
    )
    mock_sync = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.sync_agreement_subscriptions"
    )
    synchronize_agreements(mpt_client, config, None, False, "PROD-123-456")
    mock_sync.assert_not_called()


def test_sync_agreement_accounts_with_processing_subscriptions(
    mocker, mpt_client, aws_client_factory, config, agreement_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        subscriptions=[
            {"status": "Updating"},
            {"status": "Terminating"},
            {"status": "Configuring"},
        ]
    )
    mock_client.list_accounts.return_value = {"Accounts": []}
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_not_called()


def test_sync_agreement_accounts_without_processing_subscriptions(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_with_no_accounts(
    mocker, mpt_client, aws_client_factory, config, agreement_factory, mpa_pool_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )

    mock_client.list_accounts.return_value = {"Accounts": []}
    sync_agreement_subscriptions(mpt_client, aws_client, agreement_factory(), False)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_with_dry_run(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )

    mock_client.list_accounts.return_value = aws_accounts_factory()

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_with_inactive_account(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )

    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory(status="SUSPENDED")
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_with_split_billing(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(vendor_id="vendor_id")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement, mock_agreement],
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.send_error",
        return_value=None,
    )
    mocked_get_subscription_by_external_id = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_subscription_by_external_id",
        return_value=None,
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()
    mock_send_error.assert_called_once()
    mocked_get_subscription_by_external_id.assert_called_once()


def test_sync_agreement_accounts_with_split_billing_skip_subscriptions(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
    subscription_factory,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        vendor_id="vendor_id",
        subscriptions=[subscription_factory()],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement, mock_agreement],
    )

    mocked_get_subscription_by_external_id = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_subscription_by_external_id",
        return_value=subscription_factory(agreement_id="AGR-123-456", vendor_id="vendor_id"),
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.send_error",
        return_value=None,
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()
    mock_send_error.assert_not_called()
    mocked_get_subscription_by_external_id.assert_called_once()


def test_sync_agreement_accounts_subscription_already_exist(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    subscription_factory,
    product_items,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        subscriptions=[subscription_factory(vendor_id="123456789012")]
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_no_aws_item_found(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[],
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_subscription_already_exist_add_items(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    subscription_factory,
    product_items,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        subscriptions=[subscription_factory(vendor_id="123456789012", lines=[])]
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mock_update_subscription = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.update_agreement_subscription"
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()

    subscription = subscription_factory(
        vendor_id="123456789012",
        lines=[
            {
                "item": {
                    "externalIds": {"vendor": sku},
                    "id": "ITM-1234-1234-1234-0001",
                    "name": sku,
                },
                "quantity": 1,
            }
            for sku in AWS_ITEMS_SKUS
        ],
    )
    mock_update_subscription.assert_called_once_with(
        mpt_client, mock_agreement["subscriptions"][0]["id"], lines=subscription["lines"]
    )


def test_sync_agreement_accounts_subscription_already_exist_delete_items(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    subscription_factory,
    product_items,
    lines_factory,
    mpa_pool_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        subscriptions=[
            subscription_factory(
                vendor_id="123456789012",
            )
        ]
    )
    mock_agreement["subscriptions"][0]["lines"].extend(
        lines_factory(external_vendor_id="invalid", name="invalid", quantity=1)
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )

    mock_update_subscription = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.update_agreement_subscription"
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()

    mock_agreement["subscriptions"][0]["lines"].pop()
    mock_update_subscription.assert_called_once_with(
        mpt_client,
        mock_agreement["subscriptions"][0]["id"],
        lines=mock_agreement["subscriptions"][0]["lines"],
    )


def test_synchronize_agreement_with_specific_ids_exception(
    mocker, mpt_client, config, agreement_factory
):
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.AWSClient",
        side_effect=botocore.exceptions.ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}}, "TestOperation"
        ),
    )
    mock_sync = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.sync_agreement_subscriptions"
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.send_error",
        return_value=None,
    )
    synchronize_agreements(mpt_client, config, ["AGR-123-456"], False, "PROD-123-456")
    mock_sync.assert_not_called()
    mock_send_error.assert_called_once_with(
        "Synchronize AWS agreement subscriptions",
        f"Failed to synchronize agreement {mock_agreement['id']}: An error occurred (TestError) "
        f"when calling the TestOperation operation: Test error",
    )


@freeze_time("2025-05-01 11:10:00")
def test_synchronize_new_accounts_dates_test(
    mocker,
    mpt_client,
    config,
    product_items,
    aws_client_factory,
    agreement_factory,
    ffc_client,
    lines_factory,
):
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_ffc_client",
        return_value=ffc_client,
    )
    ffc_client.get_entitlement_by_datasource_id.return_value = {
        "id": "entitlement_id",
        "status": "new",
    }
    agreement_accounts = [
        {
            "Email": "test@example.com",
            "Id": "123456789012",
            "Name": "Test Account",
            "Status": "ACTIVE",
        }
    ]

    mock_create_agreement_subscription = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription"
    )

    _synchronize_new_accounts(
        mpt_client,
        mock_agreement,
        agreement_accounts,
        dry_run=False,
    )
    lines = []
    for sku in AWS_ITEMS_SKUS:
        line = lines_factory(external_vendor_id=sku, name=sku, quantity=1)
        del line[0]["id"]
        del line[0]["oldQuantity"]
        del line[0]["price"]
        lines.extend(line)

    expected_call = (
        mpt_client,
        {
            "agreement": {"id": "AGR-2119-4550-8674-5962"},
            "autoRenew": True,
            "commitmentDate": "2025-06-01T11:10:00Z",
            "externalIds": {"vendor": "123456789012"},
            "lines": lines,
            "name": "Subscription for Test Account (123456789012)",
            "parameters": {
                "fulfillment": [
                    {
                        "externalId": FulfillmentParametersEnum.ACCOUNT_EMAIL.value,
                        "value": "test@example.com",
                    },
                    {
                        "externalId": FulfillmentParametersEnum.ACCOUNT_NAME.value,
                        "value": "Test Account",
                    },
                ]
            },
            "startDate": "2025-05-01T11:10:00Z",
        },
    )

    mock_create_agreement_subscription.assert_called_once_with(*expected_call)


@freeze_time("2025-05-01 11:10:00")
def test_synchronize_new_accounts_dry_run(
    mocker, mpt_client, config, product_items, aws_client_factory, agreement_factory, ffc_client
):
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_ffc_client",
        return_value=ffc_client,
    )
    ffc_client.get_entitlement_by_datasource_id.return_value = {
        "id": "entitlement_id",
        "status": "new",
    }
    agreement_accounts = [
        {
            "Email": "test@example.com",
            "Id": "123456789012",
            "Name": "Test Account",
            "Status": "ACTIVE",
        }
    ]

    mock_create_agreement_subscription = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription"
    )

    _synchronize_new_accounts(
        mpt_client,
        mock_agreement,
        agreement_accounts,
        dry_run=True,
    )

    mock_create_agreement_subscription.assert_not_called()


def test_sync_agreement_accounts_skip_management_account(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    mpa_pool_factory,
    product_items,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )

    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    mock_agreement = agreement_factory()
    accounts = [
        {
            "Id": "Account Id",
            "Name": "Management Account",
            "Email": "management.account@email.com",
            "Status": "ACTIVE",
        },
        {
            "Id": "account_id_2",
            "Name": "Test Account 2",
            "Email": "test@example.com",
            "Status": "ACTIVE",
        },
    ]
    mock_client.list_accounts.return_value = aws_accounts_factory(accounts=accounts)
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()


def test_synchronize_agreements_exception(
    mocker,
    caplog,
    mpt_client,
    config,
    agreement_factory,
):
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.sync_agreement_subscriptions",
        side_effect=Exception("Test exception"),
    )
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_query",
        return_value=[mock_agreement],
    )

    send_error = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.send_error",
    )
    mocker.patch("swo_aws_extension.flows.jobs.synchronize_agreements.AWSClient")
    caplog.set_level("ERROR", logger="swo_aws_extension.flows.jobs.synchronize_agreements")
    agreement_ids = [mock_agreement["id"]]
    synchronize_agreements(mpt_client, config, agreement_ids, False, "PROD-123-456")
    assert "Traceback (most recent call last):" in caplog.text
    assert "Exception: Test exception" in caplog.text
    send_error.assert_called_once()
