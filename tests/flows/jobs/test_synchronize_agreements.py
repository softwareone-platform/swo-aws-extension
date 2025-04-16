from swo_aws_extension.constants import AWS_ITEM_SKU, SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.jobs.synchronize_agreements import (
    sync_agreement_subscriptions,
    synchronize_agreements,
)


def test_synchronize_agreement_with_specific_ids(
    mocker, mpt_client, config, agreement_factory, aws_client_factory
):
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_agreements_by_ids",
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
    synchronize_agreements(mpt_client, config, ["AGR-123-456"], False)
    mock_sync.assert_called_once_with(mpt_client, aws_client, mock_agreement, False)


def test_synchronize_agreement_without_ids(
    mocker, mpt_client, config, agreement_factory, aws_client_factory
):
    mock_agreement = agreement_factory(vendor_id="123456789012")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_all_agreements",
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
    synchronize_agreements(mpt_client, config, None, False)
    mock_sync.assert_called_once_with(mpt_client, aws_client, mock_agreement, False)


def test_synchronize_agreement_without_mpa(
    mocker, mpt_client, config, agreement_factory, aws_client_factory
):
    mock_agreement = agreement_factory(vendor_id="")
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_all_agreements",
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
    synchronize_agreements(mpt_client, config, None, False)
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
    mocker, mpt_client, aws_client_factory, config, agreement_factory, aws_accounts_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": mock_agreement["id"]}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )


def test_sync_agreement_accounts_with_no_accounts(
    mocker, mpt_client, aws_client_factory, config, agreement_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_client.list_accounts.return_value = {"Accounts": []}
    sync_agreement_subscriptions(mpt_client, aws_client, agreement_factory(), False)
    mock_client.list_accounts.assert_called_once()


def test_sync_agreement_accounts_with_dry_run(
    mocker, mpt_client, aws_client_factory, config, agreement_factory, aws_accounts_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": mock_agreement["id"]}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )


def test_sync_agreement_accounts_with_inactive_account(
    mocker, mpt_client, aws_client_factory, config, agreement_factory, aws_accounts_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory(status="SUSPENDED")
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_not_called()


def test_sync_agreement_accounts_with_missing_tag(
    mocker, mpt_client, aws_client_factory, config, agreement_factory, aws_accounts_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {"Tags": []}
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.send_error",
        return_value=None,
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )


def test_sync_agreement_accounts_with_wrong_agreement_id(
    mocker, mpt_client, aws_client_factory, config, agreement_factory, aws_accounts_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": "WRONG-AGREEMENT-ID"}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.create_agreement_subscription",
        return_value={"id": "SUB-123-456"},
    )
    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, False)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )


def test_sync_agreement_accounts_subscription_already_exist(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    subscription_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        subscriptions=[subscription_factory(vendor_id="123456789012")]
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": mock_agreement["id"]}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )


def test_sync_agreement_accounts_no_aws_item_found(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": mock_agreement["id"]}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=[],
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )
