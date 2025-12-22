import datetime as dt
import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_agreements_by_query

from swo_aws_extension.airtable.models import OpScaleRecord
from swo_aws_extension.airtable.op_scale_table import OpScaleEntitlementsTable
from swo_aws_extension.aws.client import MINIMUM_DAYS_MONTH, AWSClient
from swo_aws_extension.aws.config import Config
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE, OpScaleStatusEnum
from swo_aws_extension.notifications import TeamsNotificationManager
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)


class OpScaleEntitlementsProcessor:
    """Process OpScale entitlements."""

    def __init__(
        self,
        mpt_client: MPTClient,
        config: Config,
        agreement_ids: list[str],
        products_ids: list[str],
    ) -> None:
        """Initialize processor."""
        self.mpt_client = mpt_client
        self.config = config
        self.agreement_ids = agreement_ids
        self.product_ids = set(products_ids)
        self.entitlements_table = OpScaleEntitlementsTable()

    def sync(self):
        """Synchronize OpScale entitlements."""
        for agreement in self._get_agreements():
            agreement_id = agreement.get("id")
            logger.info("%s - Start processing agreement.", agreement_id)
            op_scale_entitlements = self.entitlements_table.get_by_agreement_id(agreement_id)
            logger.info(
                "%s - Found %d OpScale entitlements for agreement %s.",
                agreement_id,
                len(op_scale_entitlements),
                agreement_id,
            )
            mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
            if not mpa_account_id:
                logger.info("%s - Skipping - MPA not found", agreement_id)
                TeamsNotificationManager().send_error(
                    "Synchronize OpScale entitlements",
                    f"{agreement.get('id')} - Skipping - MPA not found",
                )
                continue
            pma_account_id = agreement["authorization"].get("externalIds", {}).get("operations")
            if not pma_account_id:
                logger.info("%s - Skipping - PMA not found", agreement_id)
                TeamsNotificationManager().send_error(
                    "Synchronize OpScale entitlements",
                    f"{agreement.get('id')} - Skipping - PMA not found",
                )
                continue

            self._synchronize_accounts(
                mpa_account_id, pma_account_id, agreement, op_scale_entitlements
            )

            self._manage_terminated_accounts(agreement_id, op_scale_entitlements)

    def _manage_terminated_accounts(self, agreement_id, op_scale_entitlements: list[OpScaleRecord]):
        for op_scale_entitlement in op_scale_entitlements:
            if op_scale_entitlement.status == OpScaleStatusEnum.TERMINATED:
                continue
            last_usage = dt.datetime.fromisoformat(op_scale_entitlement.last_usage_date)
            two_months_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=60)
            if last_usage < two_months_ago:
                logger.info(
                    "%s - Terminating OpScale entitlement for account %s due to inactivity.",
                    agreement_id,
                    op_scale_entitlement.account_id,
                )
                self.entitlements_table.update_status_and_usage_date(
                    op_scale_entitlement,
                    OpScaleStatusEnum.TERMINATED,
                    dt.datetime.now(dt.UTC).isoformat(),
                )

    def _synchronize_accounts(
        self,
        mpa_account_id: str,
        pma_account_id: str,
        agreement: dict,
        op_scale_entitlements: list[OpScaleRecord],
    ):
        aws_client = AWSClient(self.config, pma_account_id, SWO_EXTENSION_MANAGEMENT_ROLE)
        billing_views = aws_client.get_current_billing_view_by_account_id(mpa_account_id)

        for account_id in self._get_accounts_with_usage(
            agreement.get("id"), billing_views, aws_client
        ):
            exists = False
            for op_scale_entitlement in op_scale_entitlements:
                if op_scale_entitlement.account_id == account_id:
                    exists = True
                    self.entitlements_table.update_status_and_usage_date(
                        op_scale_entitlement,
                        OpScaleStatusEnum.ACTIVE,
                        dt.datetime.now(dt.UTC).isoformat(),
                    )
            if not exists:
                self.entitlements_table.save(
                    OpScaleRecord(
                        account_id=account_id,
                        buyer_id=agreement.get("buyer", {}).get("id"),
                        agreement_id=agreement.get("id"),
                        status=OpScaleStatusEnum.ACTIVE,
                        last_usage_date=dt.datetime.now(dt.UTC).isoformat(),
                    )
                )
                logger.info(
                    "%s - Created new OpScale entitlement record for account %s.",
                    agreement.get("id"),
                    account_id,
                )

    def _get_agreements(self):
        select = "&select=parameters,subscriptions,authorization.externalIds.operations"
        if self.agreement_ids:
            rql_filter = (
                RQLQuery(id__in=self.agreement_ids)
                & RQLQuery(status="Active")
                & RQLQuery(product__id__in=self.product_ids)
            )
            rql_query = f"{rql_filter}{select}"

        else:
            rql_filter = RQLQuery(status="Active") & RQLQuery(product__id__in=self.product_ids)
            rql_query = f"{rql_filter}{select}"

        return get_agreements_by_query(self.mpt_client, rql_query)

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
                    group_by=[
                        {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                    ],
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
