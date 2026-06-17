from typing import Any

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
