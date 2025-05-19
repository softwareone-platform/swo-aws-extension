import logging

import pymsteams
import pytest

from swo_aws_extension.flows.order import MPT_ORDER_STATUS_QUERYING, InitialAWSContext
from swo_aws_extension.notifications import (
    Button,
    FactsSection,
    dateformat,
    md2html,
    notify_unhandled_exception_in_teams,
    send_error,
    send_exception,
    send_notification,
    send_warning,
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

    send_notification(
        "not-title",
        "not-text",
        "not-color",
        button=button,
        facts=facts_section,
    )

    mocked_message.title.assert_called_once_with("not-title")
    mocked_message.text.assert_called_once_with("not-text")
    mocked_message.color.assert_called_once_with("not-color")
    mocked_message.addLinkButton.assert_called_once_with(button.label, button.url)
    mocked_section.title.assert_called_once_with(facts_section.title)
    mocked_section.addFact.assert_called_once_with(
        list(facts_section.data.keys())[0], list(facts_section.data.values())[0]
    )
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

    send_notification(
        "not-title",
        "not-text",
        "not-color",
    )

    mocked_message.title.assert_called_once_with("not-title")
    mocked_message.text.assert_called_once_with("not-text")
    mocked_message.color.assert_called_once_with("not-color")
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

    with caplog.at_level(logging.ERROR):
        send_notification(
            "not-title",
            "not-text",
            "not-color",
        )

    assert "Error sending notification to MSTeams!" in caplog.text


@pytest.mark.parametrize(
    ("function", "color", "icon"),
    [
        (send_warning, "#ffa500", "\u2622"),
        (send_error, "#df3422", "\U0001f4a3"),
        (send_exception, "#541c2e", "\U0001f525"),
    ],
)
def test_send_others(mocker, function, color, icon):
    mocked_send_notification = mocker.patch(
        "swo_aws_extension.notifications.send_notification",
    )

    mocked_button = mocker.MagicMock()
    mocked_facts_section = mocker.MagicMock()

    function("title", "text", button=mocked_button, facts=mocked_facts_section)

    mocked_send_notification.assert_called_once_with(
        f"{icon} title",
        "text",
        color,
        button=mocked_button,
        facts=mocked_facts_section,
    )


def test_dateformat():
    assert dateformat("2024-05-16T10:54:42.831Z") == "16 May 2024"
    assert dateformat("") == ""
    assert dateformat(None) == ""


def test_notify_unhandled_exception_in_teams(mocker):
    mocked_send_exc = mocker.patch("swo_aws_extension.notifications.send_exception")
    notify_unhandled_exception_in_teams(
        "validation",
        "ORD-0000",
        "exception-traceback",
    )

    mocked_send_exc.assert_called_once_with(
        "Order validation unhandled exception!",
        "An unhandled exception has been raised while performing validation "
        "of the order **ORD-0000**:\n\n"
        "```exception-traceback```",
    )


def test_send_mpt_notification(
    mocker,
    mpt_client,
    mpt_notifier,
    mock_get_rendered_template,
    order_factory,
    order_parameters_factory,
    buyer,
):
    """Test that MPT notification is sent correctly expected subject for order in
    querying status."""
    mock_notify = mocker.patch("swo_aws_extension.notifications.notify", spec=True)
    context = InitialAWSContext.from_order_data(
        order_factory(
            order_parameters=order_parameters_factory(),
            buyer=buyer,
            status=MPT_ORDER_STATUS_QUERYING,
        )
    )

    mpt_notifier.notify_re_order(context)

    mock_notify.assert_called_once_with(
        mpt_client,
        "NTC-0000-0006",
        "ACC-9121-8944",
        "BUY-3731-7971",
        "This order need your attention ORD-0792-5000-2253-4210 for A buyer",
        "rendered-template",
    )
    mock_get_rendered_template.assert_called_once()


def test_send_mpt_notification_exception(
    mocker,
    mpt_client,
    mpt_notifier,
    mock_get_rendered_template,
    order_factory,
    order_parameters_factory,
    buyer,
    caplog,
):
    mocker.patch(
        "swo_aws_extension.notifications.notify",
        autospec=True,
        side_effect=Exception("error"),
    )
    context = InitialAWSContext.from_order_data(
        order_factory(
            order_parameters=order_parameters_factory(),
            buyer=buyer,
            status=MPT_ORDER_STATUS_QUERYING,
        )
    )

    with caplog.at_level(logging.ERROR):
        mpt_notifier.notify_re_order(context)

        assert (
            "Cannot send MPT API notification:"
            " Category: 'NTC-0000-0006',"
            " Account ID: 'ACC-9121-8944',"
            " Buyer ID: 'BUY-3731-7971',"
            " Subject: 'This order need your attention ORD-0792-5000-2253-4210 for A buyer',"
            " Message: 'rendered-template'"
        ) in caplog.text

    mock_get_rendered_template.assert_called_once()


@pytest.fixture()
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
"""


def test_md2html(template_md):
    rendered = md2html(template_md)
    assert '<h1 style="line-height: 1.2em;">' in rendered
    assert '<h2 style="line-height: 1.2em;">' in rendered
