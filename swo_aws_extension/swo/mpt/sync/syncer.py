import logging
from typing import Any, override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    get_agreements_by_query,
    get_subscriptions_by_query,
    terminate_subscription,
    update_agreement,
)
from mpt_extension_sdk.mpt_http.wrap_http_error import wrap_mpt_http_error

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
    SubscriptionStatus,
)
from swo_aws_extension.flows.steps.crm_tickets.templates.terminate_order import (
    TRANSFER_END_SCHEDULED_TEMPLATE,
)
from swo_aws_extension.parameters import (
    get_crm_terminate_order_ticket_id,
    get_relationship_end_date,
    get_responsibility_transfer_id,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError
from swo_aws_extension.swo.mpt.sync.responsibility_transfers import (
    get_available_transfer_for_account,
    transfer_has_ended,
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

    def terminate(self, agreement: AgreementType):
        """Terminate an agreement, leaving AWS offboarding to be handled manually."""
        msg = f"{agreement.get('id')} - agreement with an inactive transfer - terminating"
        logger.warning(msg)
        TeamsNotificationManager().send_warning(self._operation_description, msg)
        self.terminate_agreement(agreement)

    def notify_scheduled_transfer_end(self, agreement: AgreementType, end_date) -> None:
        """Create the MCoE termination ticket once when the transfer end is scheduled."""
        ticket_id = get_crm_terminate_order_ticket_id(agreement)
        if ticket_id:
            logger.info(
                "%s - Transfer end already notified with ticket %s",
                agreement.get("id"),
                ticket_id,
            )
            return
        logger.warning(
            "%s - Customer has scheduled the end of the responsibility transfer for %s",
            agreement.get("id"),
            end_date,
        )
        if self.dry_run:
            logger.info(
                "%s - dry run mode - skipping termination ticket creation", agreement.get("id")
            )
            return
        ticket_id = self._create_transfer_end_ticket(agreement, end_date)
        if ticket_id:
            self._save_terminate_ticket_id(agreement, ticket_id)

    def get_available_transfer(
        self, agreement: AgreementType, mpa_account_id, pma_account_id
    ) -> dict | None:
        """Retrieve the available transfer for the given agreement and accounts."""
        try:
            return get_available_transfer_for_account(pma_account_id, mpa_account_id)
        except Exception as exception:
            msg = f"{agreement.get('id')} - Error occurred while fetching responsibility transfers"
            logger.exception(msg)
            raise AgreementProcessorError(msg, self._operation_description) from exception

    def get_pma(self, agreement: AgreementType) -> str:
        """Retrieve the PMA account ID for the given agreement."""
        pma_account_id = agreement["authorization"].get("externalIds", {}).get("operations")
        if not pma_account_id:
            msg = f"{agreement.get('id')} - Skipping - PMA not found"
            logger.error(msg)
            raise AgreementProcessorError(msg, self._operation_description)
        return str(pma_account_id)

    def get_mpa(self, agreement: AgreementType) -> str:
        """Retrieve the MPA account ID for the given agreement."""
        mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account_id:
            msg = f"{agreement.get('id')} - Skipping - MPA not found"
            logger.error(msg)
            raise AgreementProcessorError(msg, self._operation_description)
        return str(mpa_account_id)

    def sync_relationship_end_date(self, agreement: AgreementType, end_date) -> None:
        """Store the scheduled end of the responsibility transfer on the agreement."""
        end_date_value = end_date.isoformat()
        if get_relationship_end_date(agreement) == end_date_value:
            return
        logger.info(
            "%s - synchronizing relationship end date: %s",
            agreement["id"],
            end_date_value,
        )
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.RELATIONSHIP_END_DATE.value,
            end_date_value,
            error_message=(
                f"{agreement['id']} - failed to update agreement with "
                f"relationship end date {end_date_value}"
            ),
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
            "%s - synchronizing responsibility transfer ID: %s",
            agreement["id"],
            responsibility_transfer_id,
        )
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
            responsibility_transfer_id,
            error_message=(
                f"{agreement['id']} - failed to update agreement with "
                f"responsibility transfer ID {responsibility_transfer_id}"
            ),
            notification_title="Synchronize responsibility transfer ID",
        )

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
        logger.info("%s - Action - Start sync agreement", agreement.get("id"))
        mpa_account_id = self.get_mpa(agreement)
        pma_account_id = self.get_pma(agreement)

        available_transfer = self.get_available_transfer(agreement, mpa_account_id, pma_account_id)

        end_date = available_transfer.get("EndTimestamp") if available_transfer else None
        if end_date:
            self.sync_relationship_end_date(agreement, end_date)

        if not available_transfer or transfer_has_ended(available_transfer):
            self.terminate(agreement)
            return

        if end_date:
            self.notify_scheduled_transfer_end(agreement, end_date)

        self.sync_responsibility_transfer_id(agreement, available_transfer["Id"])
        logger.info("%s - End - Sync completed", agreement.get("id"))

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
            msg = f"{agreement_id} - failed to create the transfer end termination ticket"
            logger.exception(msg)
            TeamsNotificationManager().send_exception("Transfer end notification", msg)
            return None
        ticket_id = response.get("id")
        logger.info("%s - termination ticket created with ID %s", agreement_id, ticket_id)
        return ticket_id

    def _save_terminate_ticket_id(self, agreement: AgreementType, ticket_id: str) -> None:
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.CRM_TERMINATE_ORDER_TICKET_ID.value,
            ticket_id,
            error_message=(
                f"{agreement['id']} - failed to update agreement with "
                f"termination ticket ID {ticket_id}"
            ),
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
                "%s - dry run mode - skipping update with parameters: %s",
                agreement["id"],
                agreement_parameters,
            )
            return
        try:
            update_agreement(self.mpt_client, agreement["id"], parameters=agreement_parameters)
        except Exception:
            logger.exception(error_message)
            TeamsNotificationManager().send_exception(notification_title, error_message)


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
