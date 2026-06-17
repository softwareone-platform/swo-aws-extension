import datetime as dt

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from mpt_api_client.exceptions import MPTError

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
)
from swo_aws_extension.swo.mpt.sync.agreement_subscription_syncer import (
    LINKED_ACCOUNT_INACTIVITY_MONTHS,
    AgreementSubscriptionsSyncer,
)


def test_subscription_syncer_creates_new(
    agreement,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_create_agreement_subscription,
):
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]
    expected_subscription = {
        "name": "Subscription for Test Account (111111111111)",
        "autoRenew": True,
        "externalIds": {"vendor": "111111111111"},
        "agreement": {"id": "AGR-2119-4550-8674-5962"},
        "template": None,
        "lines": [{"item": {"id": "ITM-1234-1234-1234-0010"}, "quantity": 1}],
        "parameters": {"fulfillment": []},
    }

    subscription_syncer.process(agreement)  # act

    mock_create_agreement_subscription.assert_called_once()
    call_args = mock_create_agreement_subscription.call_args[0]
    subscription = call_args[1]
    assert subscription == {
        **expected_subscription,
        "startDate": subscription["startDate"],
    }


def test_subscription_syncer_skips_existing(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_create_agreement_subscription,
):
    existing_sub = {
        "id": "SUB-EXISTING",
        "status": "Active",
        "externalIds": {"vendor": "111111111111"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[existing_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer.process(agreement)  # act

    mock_create_agreement_subscription.assert_not_called()


def test_subscription_syncer_dry_run(
    agreement,
    subscription_syncer_dry_run,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_create_agreement_subscription,
):
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer_dry_run.process(agreement)  # act

    mock_create_agreement_subscription.assert_not_called()


def test_subscription_syncer_skips_terminated(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_create_agreement_subscription,
):
    terminated_sub = {
        "id": "SUB-OLD",
        "status": "Terminated",
        "externalIds": {"vendor": "111111111111"},
    }
    agreement = agreement_factory(subscriptions=[terminated_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer.process(agreement)  # act

    mock_create_agreement_subscription.assert_called_once()


def test_subscription_syncer_create_error(
    agreement,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_create_agreement_subscription,
):
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]
    mock_create_agreement_subscription.side_effect = MPTError("create failed")

    subscription_syncer.process(agreement)  # act

    assert mock_create_agreement_subscription.call_count == 1


def test_ensure_subscription_existing_no_countdown_skips_update(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_update_agreement_subscription,
):
    existing_sub = {
        "id": "SUB-EXISTING",
        "status": "Active",
        "externalIds": {"vendor": "111111111111"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[existing_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer.process(agreement)  # act

    mock_update_agreement_subscription.assert_not_called()


@freeze_time("2026-06-16")
def test_ensure_subscription_clears_countdown_when_account_active_again(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_update_agreement_subscription,
):
    existing_sub = {
        "id": "SUB-EXISTING",
        "status": "Active",
        "externalIds": {"vendor": "111111111111"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-09-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[existing_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer.process(agreement)  # act

    mock_update_agreement_subscription.assert_called_once_with(
        subscription_syncer.mpt_client,
        "SUB-EXISTING",
        parameters={
            ParamPhasesEnum.FULFILLMENT.value: [
                {"externalId": FulfillmentParametersEnum.TERMINATION_DATE.value, "value": ""}
            ]
        },
    )


def test_ensure_subscription_clears_countdown_dry_run(
    agreement_factory,
    subscription_syncer_dry_run,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_update_agreement_subscription,
):
    existing_sub = {
        "id": "SUB-EXISTING",
        "status": "Active",
        "externalIds": {"vendor": "111111111111"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-09-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[existing_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer_dry_run.process(agreement)  # act

    mock_update_agreement_subscription.assert_not_called()


def test_ensure_subscription_clears_countdown_logs_exception_on_error(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_update_agreement_subscription,
    mock_send_exception,
):
    existing_sub = {
        "id": "SUB-EXISTING",
        "status": "Active",
        "externalIds": {"vendor": "111111111111"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-09-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[existing_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]
    mock_update_agreement_subscription.side_effect = MPTError("update failed")

    subscription_syncer.process(agreement)  # act

    mock_send_exception.assert_called_once()


@freeze_time("2026-06-16")
def test_handle_inactive_subscriptions_sets_countdown(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []
    expected_date = dt.date.fromisoformat("2026-06-16") + relativedelta(
        months=LINKED_ACCOUNT_INACTIVITY_MONTHS
    )

    subscription_syncer.process(agreement)  # act

    mock_update_agreement_subscription.assert_called_once_with(
        subscription_syncer.mpt_client,
        "SUB-LINKED",
        parameters={
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": expected_date.isoformat(),
                }
            ]
        },
    )


def test_handle_inactive_subscriptions_skips_if_countdown_already_set(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-09-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer.process(agreement)  # act

    mock_update_agreement_subscription.assert_not_called()


def test_handle_inactive_subscriptions_skips_master_payer(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
):
    master_sub = {
        "id": "SUB-MASTER",
        "status": "Active",
        "externalIds": {"vendor": "225989344502"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(vendor_id="225989344502", subscriptions=[master_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer.process(agreement)  # act

    mock_update_agreement_subscription.assert_not_called()


def test_handle_inactive_subscriptions_skips_subscriptions_in_usage_list(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_product_items_by_skus,
    mock_update_agreement_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "111111111111"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = [
        {"account_id": "111111111111", "account_name": "Test Account"}
    ]

    subscription_syncer.process(agreement)  # act

    mock_update_agreement_subscription.assert_not_called()


def test_handle_inactive_subscriptions_dry_run(
    agreement_factory,
    subscription_syncer_dry_run,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer_dry_run.process(agreement)  # act

    mock_update_agreement_subscription.assert_not_called()


def test_handle_inactive_subscriptions_exception(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
    mock_send_exception,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []
    mock_update_agreement_subscription.side_effect = Exception("update failed")

    subscription_syncer.process(agreement)  # act

    mock_send_exception.assert_called_once()


@freeze_time("2026-06-16")
def test_terminate_expired_subscriptions_terminates_past_countdown(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_terminate_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-06-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer.process(agreement)  # act

    mock_terminate_subscription.assert_called_once_with(
        subscription_syncer.mpt_client,
        "SUB-LINKED",
        f"Linked account inactive: no usage for {LINKED_ACCOUNT_INACTIVITY_MONTHS} months",
    )


@freeze_time("2026-06-16")
def test_terminate_expired_subscriptions_skips_future_countdown(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_terminate_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-09-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer.process(agreement)  # act

    mock_terminate_subscription.assert_not_called()


def test_terminate_expired_subscriptions_skips_no_countdown(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
    mock_terminate_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer.process(agreement)  # act

    mock_terminate_subscription.assert_not_called()


@freeze_time("2026-06-16")
def test_terminate_expired_subscriptions_skips_master_payer(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_terminate_subscription,
):
    master_sub = {
        "id": "SUB-MASTER",
        "status": "Active",
        "externalIds": {"vendor": "225989344502"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-01-01",
                }
            ]
        },
    }
    agreement = agreement_factory(vendor_id="225989344502", subscriptions=[master_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer.process(agreement)  # act

    mock_terminate_subscription.assert_not_called()


@freeze_time("2026-06-16")
def test_terminate_expired_subscriptions_dry_run(
    agreement_factory,
    subscription_syncer_dry_run,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_terminate_subscription,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-06-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []

    subscription_syncer_dry_run.process(agreement)  # act

    mock_terminate_subscription.assert_not_called()


@freeze_time("2026-06-16")
def test_terminate_expired_subscriptions_exception(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_terminate_subscription,
    mock_send_exception,
):
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-06-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []
    mock_terminate_subscription.side_effect = Exception("terminate failed")

    subscription_syncer.process(agreement)  # act

    mock_send_exception.assert_called_once()


def test_subscription_syncer_init(mpt_client):
    syncer = AgreementSubscriptionsSyncer(mpt_client, dry_run=True)  # act

    assert syncer.mpt_client is mpt_client
    assert syncer.dry_run is True


@freeze_time("2026-06-16")
def test_handle_inactive_subscriptions_mpt_error(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_update_agreement_subscription,
    mock_send_exception,
):
    """MPTError in _set_inactivity_countdown is caught and reported."""
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {"fulfillment": []},
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []
    mock_update_agreement_subscription.side_effect = MPTError("update failed")

    subscription_syncer.process(agreement)  # act

    mock_send_exception.assert_called_once()


@freeze_time("2026-06-16")
def test_terminate_expired_subscriptions_mpt_error(
    agreement_factory,
    subscription_syncer,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_terminate_subscription,
    mock_send_exception,
):
    """MPTError in _terminate_linked_account_subscription is caught and reported."""
    linked_sub = {
        "id": "SUB-LINKED",
        "status": "Active",
        "externalIds": {"vendor": "222222222222"},
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                    "value": "2026-06-16",
                }
            ]
        },
    }
    agreement = agreement_factory(subscriptions=[linked_sub])
    mock_get_linked_accounts_with_usage.return_value = []
    mock_terminate_subscription.side_effect = MPTError("terminate failed")

    subscription_syncer.process(agreement)  # act

    mock_send_exception.assert_called_once()
