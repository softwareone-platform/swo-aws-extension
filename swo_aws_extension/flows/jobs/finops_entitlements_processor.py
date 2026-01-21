import datetime as dt
import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_agreements_by_query

from swo_aws_extension.airtable.finops_table import FinOpsEntitlementsTable
from swo_aws_extension.airtable.models import FinOpsRecord
from swo_aws_extension.aws.client import MINIMUM_DAYS_MONTH, AWSClient
from swo_aws_extension.aws.config import Config
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import FinOpsStatusEnum
from swo_aws_extension.notifications import TeamsNotificationManager
from swo_aws_extension.swo.finops.client import get_ffc_client
from swo_aws_extension.swo.finops.errors import FinOpsError
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)

NOTIFICATION_TITLE = "Synchronize FinOps entitlements"


class FinOpsEntitlementsProcessor:  # noqa: WPS214
    """Process FinOps entitlements."""

    def __init__(
        self,
        mpt_client: MPTClient,
        config: Config,
        agreement_ids: list[str],
        products_ids: list[str],
    ) -> None:
        self.mpt_client = mpt_client
        self.config = config
        self.agreement_ids = agreement_ids
        self.product_ids = set(products_ids)
        self.entitlements_table = FinOpsEntitlementsTable()
        self.finops_client = get_ffc_client()

    def sync(self):
        """Synchronize FinOps entitlements."""
        for agreement in self._get_agreements():
            agreement_id = agreement.get("id")
            logger.info("%s - Start processing agreement.", agreement_id)
            finops_entitlements = self.entitlements_table.get_by_agreement_id(agreement_id)

            mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
            if not mpa_account_id:
                logger.info("%s - Skipping - MPA not found", agreement_id)
                TeamsNotificationManager().send_error(
                    NOTIFICATION_TITLE,
                    f"{agreement_id} - Skipping - MPA not found",
                )
                continue

            pma_account_id = (
                agreement.get("authorization", {}).get("externalIds", {}).get("operations")
            )
            if not pma_account_id:
                logger.info("%s - Skipping - PMA not found", agreement_id)
                TeamsNotificationManager().send_error(
                    NOTIFICATION_TITLE,
                    f"{agreement_id} - Skipping - PMA not found",
                )
                continue

            self._synchronize_accounts(
                mpa_account_id,
                pma_account_id,
                agreement_id,
                agreement.get("buyer", {}).get("id", ""),
                finops_entitlements,
            )

            self._manage_terminated_accounts(agreement_id, finops_entitlements)

    def _manage_terminated_accounts(self, agreement_id, finops_entitlements: list[FinOpsRecord]):
        active_entitlements = [
            entitlement
            for entitlement in finops_entitlements
            if entitlement.status == FinOpsStatusEnum.ACTIVE
        ]
        for finops_entitlement in active_entitlements:
            last_usage = dt.datetime.fromisoformat(finops_entitlement.last_usage_date)
            two_months_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=60)
            if last_usage > two_months_ago:
                continue

            logger.info(
                "%s - Terminating FinOps entitlement for account %s due to inactivity.",
                agreement_id,
                finops_entitlement.account_id,
            )
            try:
                self._terminate_finops_entitlement(agreement_id, finops_entitlement)
            except FinOpsError as err:
                logger.info(
                    "%s - Error terminating FinOps entitlement for account %s: %s",
                    agreement_id,
                    finops_entitlement.account_id,
                    err,
                )
                continue
            self.entitlements_table.update_status_and_usage_date(
                finops_entitlement,
                FinOpsStatusEnum.TERMINATED,
                dt.datetime.now(dt.UTC).isoformat(),
            )

    def _synchronize_accounts(
        self,
        mpa_account_id: str,
        pma_account_id: str,
        agreement_id: str,
        buyer_id: str,
        finops_entitlements: list[FinOpsRecord],
    ):
        aws_client = AWSClient(self.config, pma_account_id, self.config.management_role_name)
        billing_views = aws_client.get_current_billing_view_by_account_id(mpa_account_id)
        accounts = self._get_accounts_with_usage(agreement_id, billing_views, aws_client)
        for account_id in accounts:
            existing = self._find_existing_entitlement(finops_entitlements, account_id)
            if existing:
                self._update_existing_entitlement(agreement_id, account_id, buyer_id, existing)

            else:
                self._create_new_entitlement(agreement_id, account_id, buyer_id)

    def _find_existing_entitlement(
        self, entitlements: list[FinOpsRecord], account_id: str
    ) -> FinOpsRecord | None:
        return next(
            (entitlement for entitlement in entitlements if entitlement.account_id == account_id),
            None,
        )

    def _create_new_entitlement(self, agreement_id: str, account_id: str, buyer_id: str):
        entitlement = self._get_or_create_entitlement_in_finops(agreement_id, account_id, buyer_id)

        self.entitlements_table.save(
            FinOpsRecord(
                account_id=account_id,
                buyer_id=buyer_id,
                agreement_id=agreement_id,
                entitlement_id=entitlement.get("id") if entitlement else None,
                status=FinOpsStatusEnum.ACTIVE,
                last_usage_date=dt.datetime.now(dt.UTC).isoformat(),
            )
        )
        logger.info(
            "%s - Created new FinOps entitlement record for account %s.", agreement_id, account_id
        )

    def _get_agreements(self):
        select = "&select=parameters,subscriptions,authorization.externalIds.operations"
        if self.agreement_ids:
            rql_filter = (
                RQLQuery(id__in=self.agreement_ids)
                & RQLQuery(status="Active")
                & RQLQuery(product__id__in=self.product_ids)
            )
        else:
            rql_filter = RQLQuery(status="Active") & RQLQuery(product__id__in=self.product_ids)
        return get_agreements_by_query(self.mpt_client, f"{rql_filter}{select}")

    def _get_accounts_with_usage(
        self, agreement_id: str, billing_views: list[dict], aws_client: AWSClient
    ) -> list[str]:
        today = dt.datetime.now(dt.UTC).date()
        next_month = today.replace(day=MINIMUM_DAYS_MONTH) + dt.timedelta(days=4)
        accounts_with_usage = []

        for billing_view in billing_views:
            try:
                cost_and_usage = aws_client.get_cost_and_usage(
                    start_date=today.replace(day=1).isoformat(),
                    end_date=next_month.replace(day=1).isoformat(),
                    view_arn=billing_view.get("arn"),
                    group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
                )
            except AWSError as error:
                logger.info(
                    "%s - Error retrieving cost and usage for billing view %s: %s",
                    agreement_id,
                    billing_view.get("arn"),
                    error,
                )
                continue
            accounts_with_usage.extend(self._get_account_keys(cost_and_usage))

        return accounts_with_usage

    def _get_account_keys(self, cost_and_usage) -> list[str]:
        keys: list[str] = []
        for period in cost_and_usage:
            for group in period.get("Groups", []):
                keys.extend(group.get("Keys", []))

        return keys

    def _get_or_create_entitlement_in_finops(
        self, agreement_id: str, account_id: str, buyer_id: str
    ) -> dict | None:
        try:
            entitlement = self.finops_client.get_entitlement_by_datasource(account_id)
        except FinOpsError as err:
            logger.info(
                "%s - Error getting entitlement from FinOps for account %s: %s",
                agreement_id,
                account_id,
                err,
            )
            return None

        if entitlement and entitlement.get("status") in {"new", "active"}:
            logger.info(
                "%s - Entitlement already exists (%s) for account id %s",
                agreement_id,
                entitlement.get("id"),
                account_id,
            )
            return entitlement

        logger.info("%s - Creating entitlement for account id %s", agreement_id, account_id)
        try:
            entitlement = self.finops_client.create_entitlement(buyer_id, account_id)
        except FinOpsError as err:
            logger.info(
                "%s - Error creating entitlement in FinOps for account %s: %s",
                agreement_id,
                account_id,
                err,
            )
            return None

        logger.info("%s - Created entitlement %s", agreement_id, entitlement.get("id"))
        return entitlement

    def _terminate_finops_entitlement(self, agreement_id, finops_entitlement):
        entitlement = self.finops_client.get_entitlement_by_datasource(
            finops_entitlement.account_id
        )
        if not entitlement:
            logger.info(
                "%s - FinOps entitlement for account %s not found in FinOps. "
                "Removing from Airtable.",
                agreement_id,
                finops_entitlement.account_id,
            )
            return
        entitlement_id = entitlement.get("id")
        if entitlement.get("status") == "new":
            self.finops_client.delete_entitlement(entitlement_id)
            logger.info("%s - Deleted FinOps entitlement %s.", agreement_id, entitlement_id)
        elif entitlement.get("status") == "active":
            self.finops_client.terminate_entitlement(entitlement_id)
            logger.info(
                "%s - Terminated FinOps entitlement %s.",
                agreement_id,
                entitlement_id,
            )

    def _update_existing_entitlement(self, agreement_id, account_id, buyer_id, existing):
        entitlement = self._get_or_create_entitlement_in_finops(agreement_id, account_id, buyer_id)
        existing.entitlement_id = entitlement.get("id") if entitlement else existing.entitlement_id
        self.entitlements_table.update_status_and_usage_date(
            existing, FinOpsStatusEnum.ACTIVE, dt.datetime.now(dt.UTC).isoformat()
        )
