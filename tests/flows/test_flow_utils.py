import logging

import pytest

from swo_aws_extension.constants import SupportTypesEnum
from swo_aws_extension.flows.flow_utils import (
    get_deploy_services_email_body,
    get_deploy_services_error_email_body,
    handle_error,
    notified_order_ids,
    send_error_ticket,
    send_services_email,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.ticket_manager import TicketManager
from swo_aws_extension.flows.steps.errors import UnexpectedStopError

MODULE = "swo_aws_extension.flows.flow_utils"


@pytest.fixture(autouse=True)
def clear_notified_order_ids():
    # Reset the in-process deduplication set between tests to prevent state leaking across test runs
    notified_order_ids.clear()


def test_get_deploy_services_email_body(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
    )
    context = PurchaseContext.from_order_data(order)

    result = get_deploy_services_email_body(context)

    assert context.order_id in result
    assert context.buyer.get("name") in result
    assert "123456789012" in result


def test_get_deploy_services_error_email_body(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
    )
    context = PurchaseContext.from_order_data(order)

    result = get_deploy_services_error_email_body(context, "something went wrong")

    assert context.order_id in result
    assert context.buyer.get("name") in result
    assert "123456789012" in result
    assert "something went wrong" in result


def test_send_services_email(mocker, caplog, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    email_manager_mock = mocker.patch(f"{MODULE}.EmailNotificationManager", autospec=True)
    email_manager_mock.return_value.send_email.return_value = True

    with caplog.at_level(logging.INFO):
        send_services_email(config, context, "email body", "log message")  # act

    email_manager_mock.return_value.send_email.assert_called_once()
    assert "log message" in caplog.text


def test_send_services_email_skips_log_on_failure(mocker, caplog, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    email_manager_mock = mocker.patch(f"{MODULE}.EmailNotificationManager", autospec=True)
    email_manager_mock.return_value.send_email.return_value = False

    with caplog.at_level(logging.INFO):
        send_services_email(config, context, "email body", "log message")  # act

    email_manager_mock.return_value.send_email.assert_called_once()
    assert "log message" not in caplog.text


def test_send_error_ticket(mocker, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    ticket_manager_mock = mocker.MagicMock(spec=TicketManager)
    mocker.patch(f"{MODULE}.TicketManager", return_value=ticket_manager_mock)

    send_error_ticket(config, context, "something went wrong")  # act

    ticket_manager_mock.create_new_ticket.assert_called_once()


def test_send_error_ticket_ignores_stop_error(mocker, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    ticket_manager_mock = mocker.MagicMock(spec=TicketManager)
    ticket_manager_mock.create_new_ticket.side_effect = UnexpectedStopError(
        "ticket failed", "details"
    )
    mocker.patch(f"{MODULE}.TicketManager", return_value=ticket_manager_mock)

    send_error_ticket(config, context, "something went wrong")  # act


def test_handle_error_skips_notifs_resold(
    mocker,
    config,
    mpt_client,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            mpa_id="123456789012",
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            feature_version_deployment_error_notified="yes"
        ),
    )
    context = PurchaseContext.from_order_data(order)
    email_mock = mocker.patch(f"{MODULE}.send_services_email", autospec=True)

    handle_error(context, config, mpt_client, "error title", "error details", "log message")  # act

    email_mock.assert_not_called()


def test_handle_error_raises_pls_if_notified(
    mocker,
    config,
    mpt_client,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            mpa_id="123456789012",
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            feature_version_deployment_error_notified="yes"
        ),
    )
    context = PurchaseContext.from_order_data(order)
    email_mock = mocker.patch(f"{MODULE}.send_services_email", autospec=True)

    with pytest.raises(UnexpectedStopError):
        handle_error(
            context, config, mpt_client, "error title", "error details", "log message"
        )  # act

    email_mock.assert_not_called()


def test_handle_error_notifies_non_pls(
    mocker,
    config,
    mpt_client,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            mpa_id="123456789012",
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(),
    )
    context = PurchaseContext.from_order_data(order)
    error_body_mock = mocker.patch(
        f"{MODULE}.get_deploy_services_error_email_body", autospec=True, return_value="error body"
    )
    email_mock = mocker.patch(f"{MODULE}.send_services_email", autospec=True)
    mocker.patch(f"{MODULE}.update_order", autospec=True, return_value=context.order)

    handle_error(context, config, mpt_client, "error title", "error details", "log message")  # act

    error_body_mock.assert_called_once_with(context, "error details")
    email_mock.assert_called_once_with(config, context, "error body", "log message")


def test_handle_error_raises_for_pls(
    mocker,
    config,
    mpt_client,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            mpa_id="123456789012",
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(),
    )
    context = PurchaseContext.from_order_data(order)
    error_body_mock = mocker.patch(
        f"{MODULE}.get_deploy_services_error_email_body", autospec=True, return_value="error body"
    )
    email_mock = mocker.patch(f"{MODULE}.send_services_email", autospec=True)
    mocker.patch(f"{MODULE}.update_order", autospec=True, return_value=context.order)

    with pytest.raises(UnexpectedStopError):
        handle_error(context, config, mpt_client, "error title", "error details", "log message")

    error_body_mock.assert_called_once_with(context, "error details")
    email_mock.assert_called_once_with(config, context, "error body", "log message")
