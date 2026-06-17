import datetime as dt
from typing import override

from dateutil.relativedelta import relativedelta
from mpt_api_client.exceptions import MPTError
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    create_agreement_subscription,
    get_product_items_by_skus,
    terminate_subscription,
    update_agreement_subscription,
)
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.aws.client import (
    MINIMUM_DAYS_MONTH,
    AWSClient,
    get_linked_accounts_with_usage,
)
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    AWS_ITEMS_SKUS,
    MPT_DATE_TIME_FORMAT,
    FulfillmentParametersEnum,
    ParamPhasesEnum,
    SubscriptionStatus,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import get_termination_date
from swo_aws_extension.swo.mpt.sync.base import AgreementProcessor, AgreementType
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = get_logger(__name__)

LINKED_ACCOUNT_INACTIVITY_MONTHS = 3


class AgreementSubscriptionsSyncer(AgreementProcessor):  # noqa: WPS214
    """Synchronizes MPT subscriptions for linked accounts within an agreement."""

    def __init__(self, mpt_client: MPTClient, *, dry_run: bool):
        self.mpt_client = mpt_client
        self.dry_run = dry_run

    @override
    @dynamic_trace_span(
        lambda _, agreement, **kwargs: f"Sync subscriptions for agreement {agreement.get('id')}"
    )
    def _process(self, agreement: AgreementType) -> None:
        mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
        pma_account_id = str(
            agreement["authorization"].get("externalIds", {}).get("operations", "")
        )
        config = get_config()
        aws_client = AWSClient(config, pma_account_id, config.management_role_name)
        linked_accounts = get_linked_accounts_with_usage(
            aws_client, mpa_account_id, self._get_billing_period(), agreement.get("id", "")
        )
        logger.info("Found %d linked accounts with usage", len(linked_accounts))
        self._sync_subscriptions(agreement, linked_accounts)
        self._terminate_expired_subscriptions(agreement)

    def _get_billing_period(self) -> BillingPeriod:
        today = dt.datetime.now(dt.UTC).date()
        next_month = today.replace(day=MINIMUM_DAYS_MONTH) + dt.timedelta(days=4)
        return BillingPeriod(
            today.replace(day=1).isoformat(), next_month.replace(day=1).isoformat()
        )

    def _sync_subscriptions(
        self, agreement: AgreementType, linked_accounts: list[dict[str, str]]
    ) -> None:
        if linked_accounts:
            subscription_items = get_product_items_by_skus(
                self.mpt_client, agreement["product"]["id"], AWS_ITEMS_SKUS
            )
            for account_info in linked_accounts:
                self._ensure_subscription(
                    agreement,
                    subscription_items,
                    account_info["account_id"],
                    account_info["account_name"],
                )

        linked_account_ids = {acc["account_id"] for acc in linked_accounts}
        self._handle_inactive_subscriptions(agreement, linked_account_ids)

    def _ensure_subscription(
        self,
        agreement: AgreementType,
        subscription_items: list[dict],
        account_id: str,
        account_name: str,
    ) -> None:
        active_statuses = {SubscriptionStatus.ACTIVE, SubscriptionStatus.UPDATING}
        existing = next(
            (
                sub
                for sub in agreement.get("subscriptions", [])
                if sub.get("externalIds", {}).get("vendor") == account_id
                and sub.get("status") in active_statuses
            ),
            None,
        )
        if existing:
            if get_termination_date(existing):
                logger.info(
                    "Linked account %s is active again - clearing countdown (%s)",
                    account_id,
                    existing["id"],
                )
                self._clear_inactivity_countdown(agreement["id"], existing["id"])
            else:
                logger.info(
                    "Subscription for linked account %s already exists (%s), skipping",
                    account_id,
                    existing["id"],
                )
            return
        if self.dry_run:
            logger.info(
                "Dry run mode - skipping subscription creation for account: %s",
                account_id,
            )
            return
        now = dt.datetime.now(dt.UTC)
        subscription = {
            "name": f"Subscription for {account_name} ({account_id})",
            "startDate": now.strftime(MPT_DATE_TIME_FORMAT),
            "autoRenew": True,
            "agreement": {"id": agreement["id"]},
            "externalIds": {"vendor": account_id},
            "template": None,
            "lines": [
                {"item": subscription_item, "quantity": 1}
                for subscription_item in subscription_items
            ],
            "parameters": {"fulfillment": []},
        }
        try:
            created = create_agreement_subscription(self.mpt_client, subscription)
        except MPTError:
            logger.warning(
                "Error creating subscription for linked account %s",
                account_id,
            )
            return
        logger.info(
            "Created subscription %s for linked account %s",
            created.get("id"),
            account_id,
        )

    def _clear_inactivity_countdown(self, agreement_id: str, subscription_id: str) -> None:
        if self.dry_run:
            logger.info(
                "Dry run mode - skipping countdown clear for subscription: %s",
                subscription_id,
            )
            return
        try:
            update_agreement_subscription(
                self.mpt_client,
                subscription_id,
                parameters={
                    ParamPhasesEnum.FULFILLMENT.value: [
                        {
                            "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                            "value": "",
                        }
                    ]
                },
            )
        except MPTError:
            msg = f"Error clearing inactivity countdown for subscription {subscription_id}"
            logger.exception(msg)
            TeamsNotificationManager().send_exception(
                f"{agreement_id} - Synchronizing MPT subscriptions for agreement", msg
            )

    def _set_inactivity_countdown(
        self, agreement_id: str, subscription_id: str, termination_date: str
    ) -> None:
        logger.info(
            "Setting inactivity countdown to %s for subscription %s",
            termination_date,
            subscription_id,
        )
        if self.dry_run:
            logger.info(
                "Dry run mode - skipping countdown set for subscription: %s",
                subscription_id,
            )
            return
        try:
            update_agreement_subscription(
                self.mpt_client,
                subscription_id,
                parameters={
                    ParamPhasesEnum.FULFILLMENT.value: [
                        {
                            "externalId": FulfillmentParametersEnum.TERMINATION_DATE.value,
                            "value": termination_date,
                        }
                    ]
                },
            )
        except MPTError:
            msg = f"Error setting inactivity countdown for subscription {subscription_id}"
            logger.exception(msg)
            TeamsNotificationManager().send_exception(
                f"{agreement_id} - Synchronizing MPT subscriptions for agreement", msg
            )

    def _terminate_linked_account_subscription(
        self, agreement_id: str, subscription_id: str
    ) -> None:
        logger.info(
            "Inactivity countdown expired for subscription %s - terminating",
            subscription_id,
        )
        if self.dry_run:
            logger.info(
                "Dry run mode - skipping subscription termination: %s",
                subscription_id,
            )
            return
        try:
            terminate_subscription(
                self.mpt_client,
                subscription_id,
                f"Linked account inactive: no usage for {LINKED_ACCOUNT_INACTIVITY_MONTHS} months",
            )
        except MPTError:
            msg = (
                f"Error terminating linked account "
                f"subscription {subscription_id} after inactivity period"
            )
            logger.exception(msg)
            TeamsNotificationManager().send_exception(
                f"{agreement_id} - Synchronizing MPT subscriptions for agreement", msg
            )

    def _get_linked_account_subscriptions(self, agreement: AgreementType) -> list[dict]:
        """Return active subscriptions for linked accounts (excludes master payer)."""
        master_payer_id = agreement.get("externalIds", {}).get("vendor", "")
        active_statuses = {SubscriptionStatus.ACTIVE, SubscriptionStatus.UPDATING}
        return [
            sub
            for sub in agreement.get("subscriptions", [])
            if sub.get("status") in active_statuses
            and sub.get("externalIds", {}).get("vendor", "")
            and sub.get("externalIds", {}).get("vendor", "") != master_payer_id
        ]

    def _handle_inactive_subscriptions(
        self, agreement: AgreementType, linked_account_ids: set[str]
    ) -> None:
        termination_date = dt.datetime.now(dt.UTC).date() + relativedelta(
            months=LINKED_ACCOUNT_INACTIVITY_MONTHS
        )

        for sub in self._get_linked_account_subscriptions(agreement):
            sub_vendor_id = sub["externalIds"]["vendor"]
            if sub_vendor_id in linked_account_ids:
                continue

            if get_termination_date(sub):
                logger.info(
                    "Inactivity countdown already set for subscription %s, skipping",
                    sub["id"],
                )
                continue
            self._set_inactivity_countdown(
                agreement.get("id", ""), sub["id"], termination_date.isoformat()
            )

    def _terminate_expired_subscriptions(self, agreement: AgreementType) -> None:
        now = dt.datetime.now(dt.UTC).date()
        for sub in self._get_linked_account_subscriptions(agreement):
            termination_date_str = (
                get_termination_date(sub)
                if sub.get("parameters", {}).get(ParamPhasesEnum.FULFILLMENT.value)
                else None
            )
            if not termination_date_str:
                continue
            if dt.date.fromisoformat(termination_date_str) > now:
                logger.info(
                    "Inactivity countdown not expired for subscription %s (expires %s)",
                    sub["id"],
                    termination_date_str,
                )
                continue
            self._terminate_linked_account_subscription(agreement.get("id", ""), sub["id"])
