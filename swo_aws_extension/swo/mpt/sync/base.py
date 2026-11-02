from typing import Any

from mpt_api_client.exceptions import MPTError
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_agreement

from swo_aws_extension.constants import ParamPhasesEnum
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = get_logger(__name__)

AgreementType = dict[str, Any]


class AgreementProcessorError(Exception):
    """Exception raised for errors during agreement synchronization."""

    def __init__(self, message: str, operation: str):
        self.message = message
        self.operation = operation
        super().__init__(f"{operation} - {message}")


class AgreementProcessor:
    """Process an agreement."""

    def __init__(self, mpt_client: MPTClient, *, dry_run: bool):
        self.mpt_client = mpt_client
        self.dry_run = dry_run

    def process(self, agreement: AgreementType) -> None:
        """Process the synchronization of a single agreement."""
        try:
            self._process(agreement)
        except AgreementProcessorError as exception:
            TeamsNotificationManager().send_warning(
                exception.operation or "AgreementProcessor", exception.message
            )
        except Exception as exception:
            msg = f"Error occurred while synchronizing agreements.\n\n\n```{exception}\n```"
            logger.exception(msg)
            TeamsNotificationManager().send_exception(
                f"Unhandled exception during agreement {agreement['id']} sync", msg
            )

    def _process(self, agreement: AgreementType) -> None:
        """Process a single agreement."""
        raise NotImplementedError

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
