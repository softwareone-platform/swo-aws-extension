import datetime as dt
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import ChannelHandshakeDeployed, FulfillmentParametersEnum
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import (
    get_billing_transfer_acceptance_date,
    get_channel_handshake_id,
    get_handshake_expiration_date,
    get_relationship_id,
)
from swo_aws_extension.swo.mpt.sync.base import AgreementProcessor, AgreementType
from swo_aws_extension.swo.mpt.sync.channel_handshakes import (
    SERVICE_TERM_RENEWAL_TITLE,
    get_fixed_commitment_end_date,
    send_service_term_renewal,
)
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = get_logger(__name__)


class AgreementParametersSyncer(AgreementProcessor):
    """Backfills empty agreement fulfillment parameters from AWS and renews service terms."""

    def __init__(
        self,
        mpt_client: MPTClient,
        *,
        dry_run: bool,
        transfer_start_date: str | None,
        pma_account_id: str,
    ):
        super().__init__(mpt_client, dry_run=dry_run)
        self.transfer_start_date = transfer_start_date
        self.pma_account_id = pma_account_id

    def sync_billing_transfer_acceptance_date(
        self, agreement: AgreementType, acceptance_date: str | None
    ) -> None:
        """Backfill an empty billing transfer acceptance date with the transfer start date."""
        if get_billing_transfer_acceptance_date(agreement):
            return
        if not acceptance_date:
            message = "Billing transfer has no start date; acceptance date not set"
            logger.warning(message)
            TeamsNotificationManager().send_warning(
                f"{agreement['id']} - Synchronize billing transfer acceptance date", message
            )
            return
        logger.info("Synchronizing billing transfer acceptance date: %s", acceptance_date)
        self._update_fulfillment_parameters(
            agreement,
            {FulfillmentParametersEnum.BILLING_TRANSFER_ACCEPTANCE_DATE.value: acceptance_date},
            error_message=(
                f"Failed to update agreement with billing transfer acceptance date "
                f"{acceptance_date}"
            ),
            notification_title="Synchronize billing transfer acceptance date",
        )

    def sync_handshake_expiration_date(self, agreement: AgreementType) -> None:
        """Backfill an empty handshake expiration date with the fixed commitment end date."""
        if get_handshake_expiration_date(agreement):
            return
        relationship_id = get_relationship_id(agreement)
        handshake_id = get_channel_handshake_id(agreement)
        if not relationship_id or not handshake_id:
            return
        commitment_end_date = get_fixed_commitment_end_date(
            agreement["id"], relationship_id, handshake_id
        )
        if not commitment_end_date:
            return
        expiration_date = commitment_end_date.isoformat()
        logger.info("Synchronizing handshake expiration date: %s", expiration_date)
        self._update_fulfillment_parameters(
            agreement,
            {FulfillmentParametersEnum.HANDSHAKE_EXPIRATION_DATE.value: expiration_date},
            error_message=(
                f"Failed to update agreement with handshake expiration date {expiration_date}"
            ),
            notification_title="Synchronize handshake expiration date",
        )

    def renew_expired_service_term(self, agreement: AgreementType) -> None:
        """Send the client a new 90-day service term once the one-year commitment has passed."""
        if not self._service_term_has_expired(agreement):
            return
        relationship_id = get_relationship_id(agreement)
        if not relationship_id:
            message = "Service term has expired but the relationship ID is missing"
            logger.warning(message)
            TeamsNotificationManager().send_warning(
                f"{agreement['id']} - {SERVICE_TERM_RENEWAL_TITLE}", message
            )
            return
        if self.dry_run:
            logger.info("Dry run mode - skipping service term renewal")
            return
        renewal = send_service_term_renewal(agreement["id"], self.pma_account_id, relationship_id)
        if not renewal:
            return
        logger.info("Service term renewal sent with channel handshake %s", renewal.handshake_id)
        # The expiration date is cleared so the next sync run doesn't send another service term.
        # A reused renewal the client already accepted is saved as approved.
        approved = (
            ChannelHandshakeDeployed.YES
            if renewal.is_accepted
            else ChannelHandshakeDeployed.NO_DEPLOYED
        )
        self._update_fulfillment_parameters(
            agreement,
            {
                FulfillmentParametersEnum.CHANNEL_HANDSHAKE_ID.value: renewal.handshake_id,
                FulfillmentParametersEnum.HANDSHAKE_EXPIRATION_DATE.value: "",
                FulfillmentParametersEnum.CHANNEL_HANDSHAKE_APPROVED.value: approved.value,
            },
            error_message=(
                f"Failed to update agreement with the renewed service term channel handshake "
                f"{renewal.handshake_id}"
            ),
            notification_title=SERVICE_TERM_RENEWAL_TITLE,
        )

    @override
    @dynamic_trace_span(
        lambda _, agreement, **kwargs: f"Sync parameters for agreement {agreement.get('id')}"
    )
    def _process(self, agreement: AgreementType) -> None:
        self.sync_billing_transfer_acceptance_date(agreement, self.transfer_start_date)
        self.sync_handshake_expiration_date(agreement)
        # MPT-27327 runs the renewal after the backfill steps.
        self.renew_expired_service_term(agreement)

    def _service_term_has_expired(self, agreement: AgreementType) -> bool:
        expiration_date = get_handshake_expiration_date(agreement)
        if not expiration_date:
            return False
        try:
            last_commitment_day = dt.datetime.fromisoformat(expiration_date).date()
        except ValueError:
            logger.warning("Invalid handshake expiration date %s", expiration_date)
            return False
        return last_commitment_day < dt.datetime.now(dt.UTC).date()
