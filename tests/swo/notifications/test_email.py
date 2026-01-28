import logging

import pytest
from botocore import exceptions as boto_exceptions

from swo_aws_extension.swo.notifications.email import EmailNotificationManager


def test_email_notification_manager_init(mocker, config):
    mock_boto3_client = mocker.patch("swo_aws_extension.swo.notifications.email.boto3.client")

    manager = EmailNotificationManager(config)  # act

    mock_boto3_client.assert_called_once_with(
        "ses",
        aws_access_key_id="access_key",
        aws_secret_access_key="secret_key",  # noqa: S106
        region_name="us-east-1",
    )
    assert manager.sender == "sender@example.com"
    assert manager.email_notifications_enabled is True


@pytest.mark.parametrize(
    "recipients",
    [
        ["recipient@example.com"],
        ["recipient1@example.com", "recipient2@example.com"],
    ],
)
def test_send_email_success(mocker, config, recipients):
    mock_ses_client = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.swo.notifications.email.boto3.client",
        return_value=mock_ses_client,
    )
    manager = EmailNotificationManager(config)

    manager.send_email(  # act
        recipient=recipients,
        subject="Test Subject",
        body="<html><body>Test Body</body></html>",
    )

    mock_ses_client.send_email.assert_called_once_with(
        Source="sender@example.com",
        Destination={
            "ToAddresses": recipients,
        },
        Message={
            "Subject": {"Data": "Test Subject", "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": "<html><body>Test Body</body></html>", "Charset": "UTF-8"},
            },
        },
    )


def test_send_email_disabled(mocker, config, settings, caplog):
    settings.EXTENSION_CONFIG = {
        **settings.EXTENSION_CONFIG,
        "EMAIL_NOTIFICATIONS_ENABLED": 0,
    }
    mock_ses_client = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.swo.notifications.email.boto3.client",
        return_value=mock_ses_client,
    )
    manager = EmailNotificationManager(config)

    with caplog.at_level(logging.INFO):
        manager.send_email(  # act
            recipient=["recipient@example.com"],
            subject="Test Subject",
            body="<html><body>Test Body</body></html>",
        )

    mock_ses_client.send_email.assert_not_called()
    assert "Email notifications are disabled" in caplog.text


def test_send_email_botocore_error(mocker, config, caplog):
    mock_ses_client = mocker.MagicMock()
    mock_ses_client.send_email.side_effect = boto_exceptions.BotoCoreError()
    mocker.patch(
        "swo_aws_extension.swo.notifications.email.boto3.client",
        return_value=mock_ses_client,
    )
    manager = EmailNotificationManager(config)

    with caplog.at_level(logging.ERROR):
        manager.send_email(  # act
            recipient=["recipient@example.com"],
            subject="Test Subject",
            body="<html><body>Test Body</body></html>",
        )

    assert "Failed to send email notification" in caplog.text
