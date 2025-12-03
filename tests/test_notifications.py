import logging
from http import HTTPStatus

import pymsteams
import pytest
from mpt_extension_sdk.mpt_http.wrap_http_error import MPTHttpError

from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_QUERYING,
    InitialAWSContext,
)
from swo_aws_extension.notifications import (
    Button,
    FactsSection,
    MPTNotificationManager,
    TeamsNotificationManager,
    dateformat,
)


def test_send_notification_full(mocker, settings):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_message = mocker.MagicMock()
    mocked_section = mocker.MagicMock()
    mocked_card = mocker.patch(
        "swo_aws_extension.notifications.pymsteams.connectorcard",
        return_value=mocked_message,
    )
    mocker.patch(
        "swo_aws_extension.notifications.pymsteams.cardsection",
        return_value=mocked_section,
    )
    button = Button("button-label", "button-url")
    facts_section = FactsSection("section-title", {"key": "value"})

    TeamsNotificationManager().send_success(
        "not-title",
        "not-text",
        button=button,
        facts=facts_section,
    )  # act

    mocked_message.title.assert_called_once_with("\u2705 not-title")
    mocked_message.text.assert_called_once_with("not-text")
    mocked_message.color.assert_called_once_with("#00FF00")
    mocked_message.addLinkButton.assert_called_once_with(button.label, button.url)
    mocked_section.title.assert_called_once_with(facts_section.title)
    mocked_section.addFact.assert_called_once_with("key", "value")
    mocked_message.addSection.assert_called_once_with(mocked_section)
    mocked_message.send.assert_called_once()
    mocked_card.assert_called_once_with("https://teams.webhook")


def test_send_notification_simple(mocker, settings):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_message = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.notifications.pymsteams.connectorcard",
        return_value=mocked_message,
    )
    mocked_cardsection = mocker.patch(
        "swo_aws_extension.notifications.pymsteams.cardsection",
    )
    teams_notification_manager = TeamsNotificationManager()

    teams_notification_manager.send_success(
        "not-title",
        "not-text",
    )  # act

    mocked_message.title.assert_called_once_with("\u2705 not-title")
    mocked_message.text.assert_called_once_with("not-text")
    mocked_message.color.assert_called_once_with("#00FF00")
    mocked_message.addLinkButton.assert_not_called()
    mocked_cardsection.assert_not_called()
    mocked_message.send.assert_called_once()


def test_send_notification_exception(mocker, settings, caplog):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_message = mocker.MagicMock()
    mocked_message.send.side_effect = pymsteams.TeamsWebhookException("error")
    mocker.patch(
        "swo_aws_extension.notifications.pymsteams.connectorcard",
        return_value=mocked_message,
    )
    teams_notification_manager = TeamsNotificationManager()

    with caplog.at_level(logging.ERROR):
        teams_notification_manager.send_success(
            "not-title",
            "not-text",
        )  # act

    assert "Error sending notification to MSTeams!" in caplog.text


@pytest.mark.parametrize(
    ("function", "color", "icon"),
    [
        (TeamsNotificationManager().send_warning, "#ffa500", "\u2622"),
        (TeamsNotificationManager().send_error, "#df3422", "\U0001f4a3"),
        (TeamsNotificationManager().send_exception, "#541c2e", "\U0001f525"),
        (TeamsNotificationManager().send_success, "#00FF00", "\u2705"),
    ],
)
def test_send_others(mocker, function, color, icon):
    mocked_send_notification = mocker.patch(
        "swo_aws_extension.notifications.TeamsNotificationManager._send_notification",
    )
    mocked_button = mocker.MagicMock()
    mocked_facts_section = mocker.MagicMock()

    function("title", "text", button=mocked_button, facts=mocked_facts_section)  # act

    mocked_send_notification.assert_called_once_with(
        f"{icon} title",
        "text",
        color,
        button=mocked_button,
        facts=mocked_facts_section,
    )


def test_dateformat():
    result = dateformat("2024-05-16T10:54:42.831Z")

    assert result == "16 May 2024"
    assert not dateformat("")
    assert not dateformat(None)


@pytest.fixture
def template_md():
    return """
# Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer pharetra dolor justo, in ornare
urna condimentum vel. Sed finibus dictum purus quis volutpat. Suspendisse vulputate tellus ut orci
efficitur maximus. Ut sit amet tempor diam. Mauris non molestie ex, eu hendrerit ligula. Curabitur
fringilla sapien ultricies purus placerat rhoncus ut a ex. Mauris a imperdiet leo. Aenean nec
ullamcorper dui, vel porttitor sem. In vel tortor nulla. Duis urna nisl, sollicitudin ut sagittis
vel, imperdiet vitae lectus. Donec quis tellus eros. Aliquam sit amet ex id neque iaculis auctor
sed vel risus.

## This is a subheading

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer pharetra dolor justo, in ornare
urna condimentum vel. Sed finibus dictum purus quis volutpat. Suspendisse vulputate tellus ut orci
efficitur maximus. Ut sit amet tempor diam. Mauris non molestie ex, eu hendrerit ligula. Curabitur
fringilla sapien ultricies purus placerat rhoncus ut a ex. Mauris a imperdiet leo. Aenean nec
ullamcorper dui, vel porttitor sem. In vel tortor nulla. Duis urna nisl, sollicitudin ut sagittis
vel, imperdiet vitae lectus. Donec quis tellus eros. Aliquam sit amet ex id neque iaculis auctor
sed vel risus.
"""  # noqa: WPS462


def test_notify_one_time_exception_in_teams(mocker):
    mocked_send_exc = mocker.patch(
        "swo_aws_extension.notifications.TeamsNotificationManager.send_exception"
    )
    teams_notification_manager = TeamsNotificationManager()

    teams_notification_manager.notify_one_time_error("title", "error-message")  # act

    mocked_send_exc.assert_called_once_with(
        "title",
        "error-message",
    )


def test_send_mpt_notification(
    mocker, mpt_client, order_factory, order_parameters_factory, settings, buyer
):
    mock_mpt_notify = mocker.patch("swo_aws_extension.notifications.notify", return_value=True)
    mock_get_rendered_template = mocker.patch(
        "swo_aws_extension.notifications.get_rendered_template",
        return_value="rendered-template",
    )
    context = InitialAWSContext.from_order_data(
        order_factory(
            order_parameters=order_parameters_factory(),
            buyer=buyer,
            status=MPT_ORDER_STATUS_QUERYING,
        )
    )
    mpt_manager = MPTNotificationManager(mpt_client)

    mpt_manager.send_notification(context)  # act

    mock_mpt_notify.assert_called_once()
    mock_get_rendered_template.assert_called_once()


def test_send_mpt_notification_error(
    mocker, mpt_client, order_factory, order_parameters_factory, settings, buyer
):
    mock_mpt_notify = mocker.patch(
        "swo_aws_extension.notifications.notify",
        side_effect=MPTHttpError(HTTPStatus.BAD_REQUEST, "Error"),
    )
    mocker.patch(
        "swo_aws_extension.notifications.get_rendered_template",
        return_value="rendered-template",
    )
    context = InitialAWSContext.from_order_data(
        order_factory(
            order_parameters=order_parameters_factory(),
            buyer=buyer,
            status=MPT_ORDER_STATUS_QUERYING,
        )
    )
    mpt_manager = MPTNotificationManager(mpt_client)

    mpt_manager.send_notification(context)  # act

    mock_mpt_notify.assert_called_once()
