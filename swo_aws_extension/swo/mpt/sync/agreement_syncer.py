from typing import override

from mpt_api_client.exceptions import MPTError
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    get_agreements_by_query,
    terminate_subscription,
    update_agreement,
)
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
    SubscriptionStatus,
)
from swo_aws_extension.flows.steps.crm_tickets.templates.terminate_order import (
    TRANSFER_END_SCHEDULED_TEMPLATE,
)
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import (
    get_crm_terminate_order_ticket_id,
    get_relationship_end_date,
    get_responsibility_transfer_id,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError
from swo_aws_extension.swo.mpt.sync.agreement_subscription_syncer import (
    AgreementSubscriptionsSyncer,
)
from swo_aws_extension.swo.mpt.sync.base import (
    AgreementProcessor,
    AgreementProcessorError,
    AgreementType,
)
from swo_aws_extension.swo.mpt.sync.responsibility_transfers import (
    get_available_transfer_for_account,
    transfer_has_ended,
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

    def terminate(self, agreement: AgreementType):
        """Terminate an agreement, leaving AWS offboarding to be handled manually."""
        msg = "Agreement with an inactive transfer - terminating"
        logger.warning(msg)
        TeamsNotificationManager().send_warning(
            f"{agreement['id']} - Synchronize AWS agreement subscriptions", msg
        )
        self.terminate_agreement(agreement)

    def notify_scheduled_transfer_end(self, agreement: AgreementType, end_date) -> None:
        """Create the MCoE termination ticket once when the transfer end is scheduled."""
        ticket_id = get_crm_terminate_order_ticket_id(agreement)
        if ticket_id:
            logger.info("Transfer end already notified with ticket %s", ticket_id)
            return
        logger.warning(
            "Customer has scheduled the end of the responsibility transfer for %s", end_date
        )
        if self.dry_run:
            logger.info("Dry run mode - skipping termination ticket creation")
            return
        ticket_id = self._create_transfer_end_ticket(agreement, end_date)
        if ticket_id:
            self._save_terminate_ticket_id(agreement, ticket_id)

    def get_available_transfer(
        self, agreement_id: str, mpa_account_id, pma_account_id
    ) -> dict | None:
        """Retrieve the available transfer for the given agreement and accounts."""
        try:
            return get_available_transfer_for_account(pma_account_id, mpa_account_id)
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

    def sync_relationship_end_date(self, agreement: AgreementType, end_date) -> None:
        """Store the scheduled end of the responsibility transfer on the agreement."""
        end_date_value = end_date.isoformat()
        if get_relationship_end_date(agreement) == end_date_value:
            return
        logger.info("Synchronizing relationship end date: %s", end_date_value)
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.RELATIONSHIP_END_DATE.value,
            end_date_value,
            error_message=f"Failed to update agreement with relationship end date {end_date_value}",
            notification_title="Synchronize relationship end date",
        )

    def sync_responsibility_transfer_id(
        self,
        agreement: AgreementType,
        responsibility_transfer_id: str,
    ) -> None:
        """Synchronizes the responsibility transfer ID for a given agreement."""
        if get_responsibility_transfer_id(agreement) == responsibility_transfer_id:
            return
        logger.info(
            "Synchronizing responsibility transfer ID: %s",
            responsibility_transfer_id,
        )
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
            responsibility_transfer_id,
            error_message=(
                f"Failed to update agreement with responsibility "
                f"transfer ID {responsibility_transfer_id}"
            ),
            notification_title="Synchronize responsibility transfer ID",
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

        available_transfer = self.get_available_transfer(
            agreement["id"], mpa_account_id, pma_account_id
        )

        end_date = available_transfer.get("EndTimestamp") if available_transfer else None
        if end_date:
            self.sync_relationship_end_date(agreement, end_date)

        if not available_transfer or transfer_has_ended(available_transfer):
            self.terminate(agreement)
            return

        if end_date:
            self.notify_scheduled_transfer_end(agreement, end_date)

        self.sync_responsibility_transfer_id(agreement, available_transfer["Id"])

        AgreementSubscriptionsSyncer(self.mpt_client, dry_run=self.dry_run).process(agreement)

        logger.info("End - Sync completed")

    def _create_transfer_end_ticket(self, agreement: AgreementType, end_date) -> str | None:
        agreement_id = agreement["id"]
        service_request = ServiceRequest(
            additional_info=TRANSFER_END_SCHEDULED_TEMPLATE.additional_info,
            summary=TRANSFER_END_SCHEDULED_TEMPLATE.summary.format(
                end_date=end_date.strftime("%Y-%m-%d %H:%M:%S"),
                agreement_id=agreement_id,
                master_payer_id=self.get_mpa(agreement),
                pma_account_id=self.get_pma(agreement),
            ),
            title=TRANSFER_END_SCHEDULED_TEMPLATE.title,
        )
        try:
            response = get_service_client().create_service_request(agreement_id, service_request)
        except CRMError:
            msg = "Failed to create the transfer end termination ticket"
            logger.exception(msg)
            TeamsNotificationManager().send_exception(
                f"{agreement_id} - Transfer end notification", msg
            )
            return None
        ticket_id = response.get("id")
        logger.info("Termination ticket created with ID %s", ticket_id)
        return ticket_id

    def _save_terminate_ticket_id(self, agreement: AgreementType, ticket_id: str) -> None:
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.CRM_TERMINATE_ORDER_TICKET_ID.value,
            ticket_id,
            error_message=f"Failed to update agreement with termination ticket ID {ticket_id}",
            notification_title="Transfer end notification",
        )

    def _update_fulfillment_parameter(
        self,
        agreement: AgreementType,
        external_id: str,
        parameter_value: str,
        *,
        error_message: str,
        notification_title: str,
    ) -> None:
        agreement_parameters = {
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": external_id,
                    "value": parameter_value,
                }
            ]
        }
        if self.dry_run:
            logger.info(
                "Dry run mode - skipping update with parameters: %s",
                agreement_parameters,
            )
            return
        agreement_id = agreement["id"]
        try:
            update_agreement(self.mpt_client, agreement_id, parameters=agreement_parameters)
        except MPTError:
            logger.exception(error_message)
            TeamsNotificationManager().send_exception(
                f"{agreement_id} - {notification_title}", error_message
            )


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
