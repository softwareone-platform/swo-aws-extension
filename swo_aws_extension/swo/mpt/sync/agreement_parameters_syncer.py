from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import FulfillmentParametersEnum
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import (
    get_billing_transfer_acceptance_date,
    get_channel_handshake_id,
    get_handshake_expiration_date,
    get_relationship_id,
)
from swo_aws_extension.swo.mpt.sync.base import AgreementProcessor, AgreementType
from swo_aws_extension.swo.mpt.sync.channel_handshakes import get_fixed_commitment_end_date
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = get_logger(__name__)


class AgreementParametersSyncer(AgreementProcessor):
    """Backfills empty agreement fulfillment parameters from AWS."""

    def __init__(
        self,
        mpt_client: MPTClient,
        *,
        dry_run: bool,
        transfer_start_date: str | None,
    ):
        super().__init__(mpt_client, dry_run=dry_run)
        self.transfer_start_date = transfer_start_date

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
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.BILLING_TRANSFER_ACCEPTANCE_DATE.value,
            acceptance_date,
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
        self._update_fulfillment_parameter(
            agreement,
            FulfillmentParametersEnum.HANDSHAKE_EXPIRATION_DATE.value,
            expiration_date,
            error_message=(
                f"Failed to update agreement with handshake expiration date {expiration_date}"
            ),
            notification_title="Synchronize handshake expiration date",
        )

    @override
    @dynamic_trace_span(
        lambda _, agreement, **kwargs: f"Sync parameters for agreement {agreement.get('id')}"
    )
    def _process(self, agreement: AgreementType) -> None:
        self.sync_billing_transfer_acceptance_date(agreement, self.transfer_start_date)
        self.sync_handshake_expiration_date(agreement)
