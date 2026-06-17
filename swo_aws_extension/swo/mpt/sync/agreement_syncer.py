from functools import cache
from typing import override

from mpt_api_client.exceptions import MPTError
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    get_agreements_by_query,
    terminate_subscription,
    update_agreement,
)
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
    ResponsibilityTransferStatus,
    SubscriptionStatus,
)
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import (
    get_billing_group_arn,
    get_relationship_id,
    get_responsibility_transfer_id,
)
from swo_aws_extension.swo.mpt.sync.agreement_subscription_syncer import (
    AgreementSubscriptionsSyncer,
)
from swo_aws_extension.swo.mpt.sync.base import (
    AgreementProcessor,
    AgreementProcessorError,
    AgreementType,
)
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager
from swo_aws_extension.swo.rql.query_builder import RQLQuery
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)


class AgreementSyncer(AgreementProcessor):  # noqa: WPS214
    """Class to synchronize MPT agreements with AWS responsibility transfers."""

    def __init__(
        self,
        mpt_client: MPTClient,
        *,
        dry_run: bool,
    ):
        self.mpt_client = mpt_client
        self.dry_run = dry_run

    def terminate(self, agreement: AgreementType, pma_account_id):
        """Terminate an agreement."""
        msg = "Agreement with an inactive transfer - terminating"
        logger.warning(msg)
        TeamsNotificationManager().send_warning(
            f"{agreement['id']} - Synchronize AWS agreement subscriptions", msg
        )
        self.terminate_agreement(agreement)
        self.delete_billing_group(agreement, pma_account_id)
        self.remove_apn(agreement, pma_account_id)

    def remove_apn(self, agreement: AgreementType, pma_account_id: str):
        """Remove the APN from the PMA account."""
        config = get_config()
        relationship_id = get_relationship_id(agreement)
        if not relationship_id:
            logger.info("Skipping - Agreement apn relationship id not set")
            return
        aws_apn_client = AWSClient(config, config.apn_account_id, config.apn_role_name)
        try:
            pm_identifier = aws_apn_client.get_program_management_id_by_account(pma_account_id)
        except AWSError:
            logger.info("Skipping - PM id not found")
            return
        if not pm_identifier:
            logger.info("Skipping - PMA identifier not found")
            return
        if self.dry_run:
            logger.info(
                "Dry run mode - skipping APN relationship deletion:"
                " relationship_id=%s pm_identifier=%s",
                relationship_id,
                pm_identifier,
            )
            return
        try:
            aws_apn_client.delete_pc_relationship(pm_identifier, relationship_id)
        except AWSError:
            logger.info(
                "Failed to delete APN relationship. relationship_id=%s pm_identifier=%s",
                relationship_id,
                pm_identifier,
            )
            return
        logger.info("APN relationship %s deleted", relationship_id)

    def get_accepted_transfer(
        self, agreement_id: str, mpa_account_id, pma_account_id
    ) -> dict | None:
        """Retrieve the accepted transfer for the given agreement and accounts."""
        try:
            return get_accepted_transfer_for_account(pma_account_id, mpa_account_id)
        except Exception as exception:
            msg = "Error occurred while fetching responsibility transfers"
            logger.exception(msg)
            raise AgreementProcessorError(
                msg, f"{agreement_id} - Synchronize AWS agreement"
            ) from exception

    def get_pma(self, agreement: AgreementType) -> str:
        """Retrieve the PMA account ID for the given agreement."""
        pma_account_id = agreement["authorization"].get("externalIds", {}).get("operations")
        if not pma_account_id:
            msg = "Skipping - PMA not found"
            logger.error(msg)
            raise AgreementProcessorError(msg, f"{agreement.get('id')} - Synchronize AWS agreement")
        return str(pma_account_id)

    def get_mpa(self, agreement: AgreementType) -> str:
        """Retrieve the MPA account ID for the given agreement."""
        mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account_id:
            msg = "Skipping - MPA not found"
            logger.error(msg)
            raise AgreementProcessorError(msg, f"{agreement.get('id')} - Synchronize AWS agreement")
        return str(mpa_account_id)

    def delete_billing_group(self, agreement: AgreementType, pma_account_id: str) -> None:
        """Deletes the billing group associated with the agreement."""
        billing_group_arn = get_billing_group_arn(agreement)
        if not billing_group_arn:
            return

        if self.dry_run:
            logger.info(
                "Dry run mode - skipping billing group deletion: %s",
                billing_group_arn,
            )
            return

        config = get_config()
        aws_client = AWSClient(config, pma_account_id, config.management_role_name)
        try:
            aws_client.delete_billing_group(billing_group_arn)
        except AWSError:
            logger.exception(
                "Failed to delete billing group %s",
                billing_group_arn,
            )
        else:
            logger.info("Billing group %s deleted", billing_group_arn)

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
            "Synchronizing responsibility transfer ID: %s",
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
                "Dry run mode - skipping update with parameters: %s",
                agreement_parameters,
            )
        else:
            try:
                update_agreement(mpt_client, agreement["id"], parameters=agreement_parameters)
            except MPTError:
                msg = (
                    f"Failed to update agreement with responsibility "
                    f"transfer ID {responsibility_transfer_id}"
                )
                logger.exception(msg)
                TeamsNotificationManager().send_exception(
                    f"{agreement['id']} - Synchronize PMA account id", msg
                )

    def terminate_agreement(self, agreement: AgreementType) -> None:
        """Terminates agreement by terminating all its active subscriptions."""
        mpt_client = self.mpt_client
        subscription_ids = [
            sub["id"]
            for sub in agreement["subscriptions"]
            if sub["status"] != SubscriptionStatus.TERMINATED
        ]
        for subscription_id in subscription_ids:
            logger.info(
                "Terminating agreement due to inactive transfer - terminating subscription %s.",
                subscription_id,
            )
            if self.dry_run:
                logger.info(
                    "Terminating agreement due to inactive transfer - dry run - skipping.",
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
                        "Terminating agreement due to inactive transfer -"
                        f" error terminating subscription {subscription_id}."
                    )
                    logger.exception(msg)
                    TeamsNotificationManager().send_exception(
                        f"{agreement['id']} - Inactive transfer", msg
                    )

    @with_log_context(lambda _, agreement, **kwargs: agreement.get("id"))
    @dynamic_trace_span(
        lambda _, agreement, **kwargs: f"Sync subscriptions for agreement {agreement.get('id')}"
    )
    @override
    def _process(self, agreement: AgreementType) -> None:
        logger.info("Action - Start sync agreement")
        mpa_account_id = self.get_mpa(agreement)
        pma_account_id = self.get_pma(agreement)

        accepted_transfer = self.get_accepted_transfer(
            agreement["id"], mpa_account_id, pma_account_id
        )

        if not accepted_transfer:
            self.terminate(agreement, pma_account_id)
            return

        self.sync_responsibility_transfer_id(self.mpt_client, agreement, accepted_transfer["Id"])

        AgreementSubscriptionsSyncer(self.mpt_client, dry_run=self.dry_run).process(agreement)

        logger.info("End - Sync completed")


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
    select = (
        "&select=parameters,subscriptions.parameters"
        ",subscriptions,authorization.externalIds.operations"
    )
    if agreement_ids:
        rql_query = (
            RQLQuery(id__in=agreement_ids)
            & RQLQuery(status="Active")
            & RQLQuery(product__id__in=product_ids)
        )
        rql_query = f"{rql_query}{select}"

    else:
        rql_query = RQLQuery(status="Active") & RQLQuery(product__id__in=product_ids)
        rql_query = f"{rql_query}{select}"

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
