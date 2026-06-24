import logging

import pytest
import requests

from swo_aws_extension.swo.notifications.teams import (
    Button,
    FactsSection,
    Style,
    TeamsNotificationManager,
    notify_one_time_error,
)


def test_send_notification_full(mocker, settings):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_post = mocker.patch(
        "swo_aws_extension.swo.notifications.teams.requests.post",
    )
    button = Button("button-label", "button-url")
    facts_section = FactsSection("section-title", {"key": "value"})

    TeamsNotificationManager().send_success(
        "not-title",
        "not-text",
        button=button,
        facts=facts_section,
    )  # act

    mocked_post.assert_called_once()
    call_args = mocked_post.call_args
    assert call_args.args[0] == "https://teams.webhook"
    assert isinstance(call_args.kwargs["timeout"], int)
    payload = call_args.kwargs["json"]
    card = payload["attachments"][0]["content"]
    card_body = card["body"]
    title_container = card_body[0]["items"][0]
    fact_sets = [block for block in card_body if block.get("type") == "FactSet"]
    expected = {
        "payload_type": "message",
        "card_type": "AdaptiveCard",
        "body_text": "not-text",
        "actions": [
            {"type": "Action.OpenUrl", "title": "button-label", "url": "button-url"},
        ],
        "facts": [{"title": "key", "value": "value"}],
    }
    assert (
        payload["type"],
        card["type"],
        card_body[1]["text"],
        card["actions"],
        fact_sets[0]["facts"],
    ) == (
        expected["payload_type"],
        expected["card_type"],
        expected["body_text"],
        expected["actions"],
        expected["facts"],
    )
    assert "✅ not-title" in title_container["text"]
    assert any(block.get("text") == "section-title" for block in card_body)


def test_send_notification_simple(mocker, settings):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_post = mocker.patch(
        "swo_aws_extension.swo.notifications.teams.requests.post",
    )

    TeamsNotificationManager().send_success("not-title", "not-text")  # act

    mocked_post.assert_called_once()
    payload = mocked_post.call_args.kwargs["json"]
    card = payload["attachments"][0]["content"]
    assert "actions" not in card
    assert len(card["body"]) == 2


def test_send_notification_exception(mocker, settings, caplog):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_post = mocker.patch(
        "swo_aws_extension.swo.notifications.teams.requests.post",
    )
    mocked_post.side_effect = requests.RequestException("error")

    with caplog.at_level(logging.ERROR):
        TeamsNotificationManager().send_success("not-title", "not-text")  # act

    assert "Error sending notification to MSTeams!" in caplog.text


def test_send_notification_exception_on_raise_for_status(mocker, settings, caplog):
    settings.EXTENSION_CONFIG = {
        "MSTEAMS_WEBHOOK_URL": "https://teams.webhook",
    }
    mocked_post = mocker.patch(
        "swo_aws_extension.swo.notifications.teams.requests.post",
    )
    mocked_post.return_value.raise_for_status.side_effect = requests.HTTPError("bad status")

    with caplog.at_level(logging.ERROR):
        TeamsNotificationManager().send_success("not-title", "not-text")  # act

    assert "Error sending notification to MSTeams!" in caplog.text


@pytest.mark.parametrize(
    ("function", "style", "icon"),
    [
        (TeamsNotificationManager().send_warning, Style.WARNING, "☢"),
        (TeamsNotificationManager().send_error, Style.ATTENTION, "\U0001f4a3"),
        (TeamsNotificationManager().send_exception, Style.ATTENTION, "\U0001f525"),
        (TeamsNotificationManager().send_success, Style.SUCCESS, "✅"),
    ],
)
def test_send_others(mocker, function, style, icon):
    mocked_send_notification = mocker.patch(
        "swo_aws_extension.swo.notifications.teams.TeamsNotificationManager._send_notification",
    )
    mocked_button = mocker.MagicMock()
    mocked_facts_section = mocker.MagicMock()

    function("title", "text", button=mocked_button, facts=mocked_facts_section)  # act

    mocked_send_notification.assert_called_once_with(
        f"{icon} title",
        "text",
        style,
        button=mocked_button,
        facts=mocked_facts_section,
    )


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
        "swo_aws_extension.swo.notifications.teams.TeamsNotificationManager.send_exception"
    )

    notify_one_time_error("title", "error-message")  # act

    mocked_send_exc.assert_called_once_with(
        "title",
        "error-message",
    )
