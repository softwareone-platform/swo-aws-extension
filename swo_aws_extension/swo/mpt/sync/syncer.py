import logging
from functools import cache
from typing import Any, override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    get_agreements_by_query,
    get_subscriptions_by_query,
    terminate_subscription,
    update_agreement,
)
from mpt_extension_sdk.mpt_http.wrap_http_error import wrap_mpt_http_error

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
    ResponsibilityTransferStatus,
    SubscriptionStatus,
)
from swo_aws_extension.parameters import (
    get_billing_group_arn,
    get_relationship_id,
    get_responsibility_transfer_id,
)
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)


AgreementType = dict[str, Any]


class AgreementProcessorError(Exception):
    """Exception raised for errors during agreement synchronization."""

    def __init__(self, message: str, operation: str):
        self.message = message
        self.operation = operation
        super().__init__(f"{operation} - {message}")


class AgreementProcessor:
    """Process an agreement."""

    def process(self, agreement: AgreementType) -> None:
        """Process the synchronization of a single agreement."""
        try:
            self._process(agreement)
        except AgreementProcessorError as exception:
            TeamsNotificationManager().send_warning(
                exception.operation or "AgreementProcessor", exception.message
            )
        except Exception as exception:
            msg = (
                f"{agreement.get('id')} - Error occurred while synchronizing agreements."
                f"\n\n\n```{exception}\n```"
            )
            logger.exception(msg)
            TeamsNotificationManager().send_exception(
                "Unhandled exception during agreement sync", msg
            )

    def _process(self, agreement: AgreementType) -> None:
        """Process a single agreement."""
        raise NotImplementedError


class AgreementSyncer(AgreementProcessor):  # noqa: WPS214
    """Class to synchronize MPT agreements with AWS responsibility transfers."""

    def __init__(
        self,
        mpt_client: MPTClient,
        *,
        dry_run: bool,
    ):
        self.mpt_client = mpt_client
        self._operation_description = "Synchronize AWS agreement subscriptions"
        self.dry_run = dry_run

    def terminate(self, agreement: AgreementType, pma_account_id):
        """Terminate an agreement."""
        msg = f"{agreement.get('id')} - agreement with an inactive transfer - terminating"
        logger.warning(msg)
        TeamsNotificationManager().send_warning(self._operation_description, msg)
        self.terminate_agreement(agreement)
        self.delete_billing_group(agreement, pma_account_id)
        self.remove_apn(agreement, pma_account_id)

    def remove_apn(self, agreement: AgreementType, pma_account_id: str):
        """Remove the APN from the PMA account."""
        config = get_config()
        relationship_id = get_relationship_id(agreement)
        if not relationship_id:
            logger.info(
                "%s - Skipping - Agreement apn relationship id not set", agreement.get("id")
            )
            return
        aws_apn_client = AWSClient(config, config.apn_account_id, config.apn_role_name)
        try:
            pm_identifier = aws_apn_client.get_program_management_id_by_account(pma_account_id)
        except AWSError:
            logger.info("%s - Skipping - PM id not found", agreement.get("id"))
            return
        if not pm_identifier:
            logger.info("%s - Skipping - PMA identifier not found", agreement.get("id"))
            return
        if self.dry_run:
            logger.info(
                "%s - dry run mode - skipping APN relationship deletion:"
                " relationship_id=%s pm_identifier=%s",
                agreement.get("id"),
                relationship_id,
                pm_identifier,
            )
            return
        try:
            aws_apn_client.delete_pc_relationship(pm_identifier, relationship_id)
        except AWSError:
            logger.info(
                "%s - Failed to delete APN relationship. relationship_id=%s pm_identifier=%s",
                agreement.get("id"),
                relationship_id,
                pm_identifier,
            )

    def get_accepted_transfer(
        self, agreement: AgreementType, mpa_account_id, pma_account_id
    ) -> dict | None:
        """Retrieve the accepted transfer for the given agreement and accounts."""
        try:
            return get_accepted_transfer_for_account(pma_account_id, mpa_account_id)
        except Exception as exception:
            msg = f"{agreement.get('id')} - Error occurred while fetching responsibility transfers"
            logger.exception(msg)
            raise AgreementProcessorError(
                msg, "AgreementSyncer.get_accepted_transfer"
            ) from exception

    def get_pma(self, agreement: AgreementType) -> str:
        """Retrieve the PMA account ID for the given agreement."""
        pma_account_id = agreement["authorization"].get("externalIds", {}).get("operations")
        if not pma_account_id:
            msg = f"{agreement.get('id')} - Skipping - PMA not found"
            logger.error(msg)
            raise AgreementProcessorError(msg, "AgreementSyncer.get_pma")
        return str(pma_account_id)

    def get_mpa(self, agreement: AgreementType) -> str:
        """Retrieve the MPA account ID for the given agreement."""
        mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account_id:
            msg = f"{agreement.get('id')} - Skipping - MPA not found"
            logger.error(msg)
            raise AgreementProcessorError(msg, "AgreementSyncer.get_mpa")
        return str(mpa_account_id)

    def delete_billing_group(self, agreement: AgreementType, pma_account_id: str) -> None:
        """Deletes the billing group associated with the agreement."""
        billing_group_arn = get_billing_group_arn(agreement)
        if not billing_group_arn:
            return

        if self.dry_run:
            logger.info(
                "%s - dry run mode - skipping billing group deletion: %s",
                agreement["id"],
                billing_group_arn,
            )
            return

        config = get_config()
        aws_client = AWSClient(config, pma_account_id, config.management_role_name)
        try:
            aws_client.delete_billing_group(billing_group_arn)
        except AWSError:
            logger.exception(
                "%s - Failed to delete billing group %s",
                agreement["id"],
                billing_group_arn,
            )
        else:
            logger.info("%s - Billing group %s deleted", agreement["id"], billing_group_arn)

    def sync_responsibility_transfer_id(
        self,
        mpt_client: MPTClient,
        agreement: AgreementType,
        responsibility_transfer_id: str,
    ) -> None:
        """Synchronizes the PMA account ID for a given agreement."""
        if get_responsibility_transfer_id(agreement) == responsibility_transfer_id:
            return
        logger.info(
            "%s - synchronizing responsibility transfer ID: %s",
            agreement["id"],
            responsibility_transfer_id,
        )
        agreement_parameters = {
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
                    "value": responsibility_transfer_id,
                }
            ]
        }
        if self.dry_run:
            logger.info(
                "%s - dry run mode - skipping update with parameters: %s",
                agreement["id"],
                agreement_parameters,
            )
        else:
            try:
                update_agreement(mpt_client, agreement["id"], parameters=agreement_parameters)
            except Exception:
                msg = (
                    f"{agreement['id']} - failed to update agreement with "
                    f"responsibility transfer ID {responsibility_transfer_id}"
                )
                logger.exception(msg)
                TeamsNotificationManager().send_exception("Synchronize PMA account id", msg)

    def terminate_agreement(self, agreement: AgreementType) -> None:
        """Terminates agreement by terminating all its active subscriptions."""
        mpt_client = self.mpt_client
        agreement_id = agreement["id"]
        subscription_ids = [
            sub["id"]
            for sub in agreement["subscriptions"]
            if sub["status"] != SubscriptionStatus.TERMINATED
        ]
        for subscription_id in subscription_ids:
            logger.info(
                "%s - terminating agreement due to inactive transfer - "
                "terminating subscription %s.",
                agreement_id,
                subscription_id,
            )
            if self.dry_run:
                logger.info(
                    "%s - terminating agreement due to inactive transfer - dry run - skipping.",
                    agreement_id,
                )
            else:
                try:
                    terminate_subscription(
                        mpt_client,
                        subscription_id,
                        "Suspected Lost Customer",
                    )
                except Exception:
                    msg = (
                        f"{agreement_id} - terminating agreement due to inactive transfer -"
                        f" error terminating subscription {subscription_id}."
                    )
                    logger.exception(msg)
                    TeamsNotificationManager().send_exception("Inactive transfer", msg)

    @override
    def _process(self, agreement: AgreementType) -> None:
        mpa_account_id = self.get_mpa(agreement)
        pma_account_id = self.get_pma(agreement)

        accepted_transfer = self.get_accepted_transfer(agreement, mpa_account_id, pma_account_id)

        if not accepted_transfer:
            self.terminate(agreement, pma_account_id)
            return

        self.sync_responsibility_transfer_id(self.mpt_client, agreement, accepted_transfer["Id"])


# TODO: SDK candidate
@wrap_mpt_http_error
def get_subscription_by_external_id(mpt_client, subscription_external_id):  # pragma: no cover
    """
    Get the first subscription for a specific external ID.

    Args:
        mpt_client: The MPT client.
        subscription_external_id: The external ID of the subscription.

    Returns:
        dict: The first subscription that matches the external ID.
    """
    select = "&select=agreement.id&limit=1"
    rql_filter = RQLQuery("externalIds.vendor").eq(subscription_external_id) & RQLQuery(
        status__in=("Active", "Updating")
    )
    rql_query = f"{rql_filter}{select}"

    response = get_subscriptions_by_query(mpt_client, rql_query)

    response.raise_for_status()
    subscriptions = response.json()
    return subscriptions["data"][0] if subscriptions["data"] else None


@cache
def get_accepted_inbound_responsibility_transfers(pma_account_id: str) -> dict:
    """Fetches ACCEPTED inbound responsibility transfers from the specified AWS client.

    Args:
        pma_account_id: The PMA account ID to query transfers from.

    Returns:
        A dict mapping source ManagementAccountId to the ACCEPTED transfer info.
    """
    config = get_config()
    aws_client = AWSClient(config, pma_account_id, config.management_role_name)
    result = {}
    for rt in aws_client.get_inbound_responsibility_transfers():
        if rt.get("Status") != ResponsibilityTransferStatus.ACCEPTED.value:
            continue
        source_account_id = rt.get("Source", {}).get("ManagementAccountId")
        if not source_account_id:
            continue
        result[source_account_id] = {"Id": rt["Id"], "Status": rt["Status"]}

    return result


def synchronize_agreements(
    mpt_client: MPTClient,
    agreement_ids: list[str],
    product_ids: list[str],
    *,
    dry_run: bool,
) -> None:
    """
    Synchronize all agreements.

    Args:
        mpt_client: The MPT client.
        agreement_ids: List of specific agreement IDs to synchronize.
        product_ids: List of product IDs to filter agreements.
        dry_run: Whether to perform a dry run.
    """
    product_ids = set(product_ids)
    select = "&select=parameters,subscriptions,authorization.externalIds.operations"
    if agreement_ids:
        rql_filter = (
            RQLQuery(id__in=agreement_ids)
            & RQLQuery(status="Active")
            & RQLQuery(product__id__in=product_ids)
        )
        rql_query = f"{rql_filter}{select}"

    else:
        rql_filter = RQLQuery(status="Active") & RQLQuery(product__id__in=product_ids)
        rql_query = f"{rql_filter}{select}"

    syncer = AgreementSyncer(
        mpt_client,
        dry_run=dry_run,
    )
    for agreement in get_agreements_by_query(mpt_client, rql_query):
        syncer.process(agreement)


def get_accepted_transfer_for_account(
    pma_account_id: str, source_management_account_id: str
) -> dict | None:
    """
    Get the ACCEPTED inbound responsibility transfer for a specific source account.

    Args:
        pma_account_id: The PMA account ID to query transfers from.
        source_management_account_id: The source ManagementAccountId to filter by.

    Returns:
        The transfer dict if found with ACCEPTED status, None otherwise.
    """
    accepted_transfers = get_accepted_inbound_responsibility_transfers(pma_account_id)
    return accepted_transfers.get(source_management_account_id)
