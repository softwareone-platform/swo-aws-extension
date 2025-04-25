import botocore.exceptions
from freezegun import freeze_time

from swo_aws_extension.constants import (
    AWS_ITEMS_SKUS,
    SWO_EXTENSION_MANAGEMENT_ROLE,
    AccountTypesEnum,
    SupportTypesEnum,
    TerminationParameterChoices,
)
from swo_aws_extension.flows.jobs.synchronize_agreements import (
    _synchronize_new_accounts,
    sync_agreement_subscriptions,
    synchronize_agreements,
)
from swo_aws_extension.parameters import FulfillmentParametersEnum, OrderParametersEnum


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
        return_value=product_items,
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
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
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
        return_value=product_items,
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
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory()
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {"Tags": []}
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
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
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    product_items,
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
        return_value=product_items,
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
    product_items,
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
        return_value=product_items,
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


def test_sync_agreement_accounts_subscription_already_exist_add_items(
    mocker,
    mpt_client,
    aws_client_factory,
    config,
    agreement_factory,
    aws_accounts_factory,
    subscription_factory,
    product_items,
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_agreement = agreement_factory(
        subscriptions=[subscription_factory(vendor_id="123456789012", lines=[])]
    )
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": mock_agreement["id"]}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mock_update_subscription = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.update_agreement_subscription"
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )

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
    mock_client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": "agreement_id", "Value": mock_agreement["id"]}]
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mock_update_subscription = mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.update_agreement_subscription"
    )

    sync_agreement_subscriptions(mpt_client, aws_client, mock_agreement, True)
    mock_client.list_accounts.assert_called_once()
    mock_client.list_tags_for_resource.assert_called_once_with(
        ResourceId=aws_accounts_factory()["Accounts"][0]["Id"]
    )
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
def test__synchronize_new_accounts_dates_test(
    mocker, mpt_client, config, product_items, aws_client_factory
):
    mocker.patch(
        "swo_aws_extension.flows.jobs.synchronize_agreements.get_product_items_by_skus",
        return_value=product_items,
    )
    mock_agreement = {
        "audit": {
            "created": {"at": "2023-12-14T18:02:16.9359", "by": {"id": "USR-0000-0001"}},
            "updated": None,
        },
        "authorization": {"id": "AUT-1234-5678"},
        "buyer": {
            "address": {
                "addressLine1": "3601 Lyon St",
                "addressLine2": "",
                "city": "San Jose",
                "country": "US",
                "postCode": "94123",
                "state": "CA",
            },
            "contact": {
                "email": "francesco.faraone@softwareone.com",
                "firstName": "Cic",
                "lastName": "Faraone",
                "phone": {"number": "4082954078", "prefix": "+1"},
            },
            "externalIds": {
                "accountExternalId": "US-999999",
                "erpCompanyContact": "US-CON-111111",
                "erpCustomer": "US-SCU-111111",
            },
            "href": "/accounts/buyers/BUY-3731-7971",
            "icon": "/static/BUY-3731-7971/icon.png",
            "id": "BUY-3731-7971",
            "name": "A buyer",
        },
        "client": {
            "href": "/accounts/sellers/ACC-9121-8944",
            "icon": "/static/ACC-9121-8944/icon.png",
            "id": "ACC-9121-8944",
            "name": "Software LN",
        },
        "externalIds": {"vendor": ""},
        "href": "/commerce/agreements/AGR-2119-4550-8674-5962",
        "icon": None,
        "id": "AGR-2119-4550-8674-5962",
        "licensee": {"address": None, "name": "My beautiful licensee", "useBuyerAddress": False},
        "lines": [],
        "listing": {
            "href": "/listing/LST-9401-9279",
            "id": "LST-9401-9279",
            "priceList": {
                "currency": "USD",
                "href": "/v1/price-lists/PRC-9457-4272-3691",
                "id": "PRC-9457-4272-3691",
            },
        },
        "name": "Product Name 1",
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.PHASE,
                    "id": "PAR-1234-5678",
                    "name": "Phase",
                    "type": "Dropdown",
                    "value": "",
                },
                {
                    "externalId": FulfillmentParametersEnum.ACCOUNT_REQUEST_ID,
                    "id": "PAR-1234-5679",
                    "name": "Account Request ID",
                    "type": "SingleLineText",
                    "value": "",
                },
                {
                    "externalId": FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID,
                    "id": "PAR-1234-5677",
                    "name": "Service Now Ticket for Link Account",
                    "type": "SingleLineText",
                    "value": "",
                },
                {
                    "externalId": FulfillmentParametersEnum.CCP_ENGAGEMENT_ID,
                    "id": "PAR-1234-5679",
                    "name": "CCP Engagement ID",
                    "type": "SingleLineText",
                    "value": "",
                },
            ],
            "ordering": [
                {
                    "constraints": {"hidden": True, "readonly": False, "required": False},
                    "externalId": OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                    "id": "PAR-1234-5678",
                    "name": "AWS account email",
                    "type": "SingleLineText",
                    "value": "test@aws.com",
                },
                {
                    "constraints": {"hidden": True, "readonly": False, "required": False},
                    "externalId": OrderParametersEnum.ACCOUNT_NAME,
                    "id": "PAR-1234-5679",
                    "name": "Account Name",
                    "type": "SingleLineText",
                    "value": "account_name",
                },
                {
                    "constraints": {"hidden": True, "readonly": False, "required": False},
                    "externalId": OrderParametersEnum.ACCOUNT_TYPE,
                    "id": "PAR-1234-5680",
                    "name": "Account type",
                    "type": "choice",
                    "value": AccountTypesEnum.NEW_ACCOUNT,
                },
                {
                    "constraints": {"hidden": True, "readonly": False, "required": False},
                    "externalId": OrderParametersEnum.ACCOUNT_ID,
                    "id": "PAR-1234-5681",
                    "name": "Account ID",
                    "type": "SingleLineText",
                    "value": "account_id",
                },
                {
                    "externalId": OrderParametersEnum.TERMINATION,
                    "id": "PAR-1234-5678",
                    "name": "Account Termination Type",
                    "type": "Choice",
                    "value": TerminationParameterChoices.CLOSE_ACCOUNT,
                },
                {
                    "externalId": OrderParametersEnum.SUPPORT_TYPE,
                    "id": "PAR-1234-5679",
                    "name": "Support Type",
                    "type": "Choice",
                    "value": SupportTypesEnum.PARTNER_LED_SUPPORT,
                },
                {
                    "externalId": OrderParametersEnum.TRANSFER_TYPE,
                    "id": "PAR-1234-5680",
                    "name": "Transfer Type",
                    "type": "Choice",
                    "value": None,
                },
                {
                    "externalId": OrderParametersEnum.MASTER_PAYER_ID,
                    "id": "PAR-1234-5681",
                    "name": "Master Payer ID",
                    "type": "SingleLineText",
                    "value": None,
                },
                {
                    "externalId": OrderParametersEnum.CONTACT,
                    "id": "PAR-1234-5681",
                    "name": "Master Payer ID",
                    "type": "Contact",
                    "value": None,
                },
            ],
        },
        "product": {"id": "PRD-1111-1111"},
        "seller": {
            "address": {"country": "US"},
            "href": "/accounts/sellers/SEL-9121-8944",
            "icon": "/static/SEL-9121-8944/icon.png",
            "id": "SEL-9121-8944",
            "name": "SWO US",
        },
        "subscriptions": [
            {"id": "SUB-1000-2000-3000", "item": {"id": "ITM-0000-0001-0001"}, "status": "Active"},
            {"id": "SUB-1234-5678", "item": {"id": "ITM-0000-0001-0002"}, "status": "Terminated"},
        ],
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

    expected_call = (
        mpt_client,
        {
            "agreement": {"id": "AGR-2119-4550-8674-5962"},
            "autoRenew": True,
            "commitmentDate": "2025-06-01T11:10:00Z",
            "externalIds": {"vendor": "123456789012"},
            "lines": [
                {
                    "item": {
                        "externalIds": {"vendor": "AWS Usage"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "AWS Usage",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "AWS Marketplace"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "AWS Marketplace",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "AWS Usage incentivate"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "AWS Usage incentivate",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "AWS Other services"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "AWS Other services",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "AWS Support Enterprise"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "AWS Support Enterprise",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "Upfront"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "Upfront",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "AWS Support"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "AWS Support",
                    },
                    "quantity": 1,
                },
                {
                    "item": {
                        "externalIds": {"vendor": "Saving Plans Recurring Fee"},
                        "id": "ITM-1234-1234-1234-0001",
                        "name": "Saving Plans Recurring Fee",
                    },
                    "quantity": 1,
                },
            ],
            "name": "Subscription for Test Account (123456789012)",
            "parameters": {
                "fulfillment": [
                    {
                        "externalId": FulfillmentParametersEnum.ACCOUNT_EMAIL,
                        "value": "test@example.com",
                    },
                    {"externalId": FulfillmentParametersEnum.ACCOUNT_NAME, "value": "Test Account"},
                ]
            },
            "startDate": "2025-05-01T11:10:00Z",
        },
    )

    mock_create_agreement_subscription.assert_called_once_with(*expected_call)
