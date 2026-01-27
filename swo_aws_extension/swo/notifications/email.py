import logging

import boto3
from botocore import exceptions as boto_exceptions

from swo_aws_extension.config import Config

logger = logging.getLogger(__name__)


class EmailNotificationManager:
    """Notification manager used by business logic to send email notifications via AWS SES."""

    def __init__(self, config: Config) -> None:
        access_key = config.aws_ses_access_key
        secret_key = config.aws_ses_secret_key
        self.client = boto3.client(
            "ses",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=config.aws_ses_region,
        )
        self.sender = config.email_notifications_sender
        self.email_notifications_enabled = config.email_notifications_enabled

    def send_email(
        self,
        recipient: list[str],
        subject: str,
        body: str,
    ) -> None:
        """Send an email notification using a template."""
        if not self.email_notifications_enabled:
            logger.info("Email notifications are disabled. Skipping sending email.")
            return
        try:
            self.client.send_email(
                Source=self.sender,
                Destination={
                    "ToAddresses": recipient,
                },
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": body, "Charset": "UTF-8"},
                    },
                },
            )
        except (boto_exceptions.ClientError, boto_exceptions.BotoCoreError):
            logger.exception("Failed to send email notification")
