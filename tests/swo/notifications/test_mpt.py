from http import HTTPStatus

from mpt_extension_sdk.mpt_http.wrap_http_error import MPTHttpError

from swo_aws_extension.flows.order import (
    InitialAWSContext,
)
from swo_aws_extension.flows.order_utils import MPT_ORDER_STATUS_QUERYING
from swo_aws_extension.swo.notifications.mpt import MPTNotificationManager, dateformat


def test_dateformat():
    result = dateformat("2024-05-16T10:54:42.831Z")

    assert result == "16 May 2024"
    assert not dateformat("")
    assert not dateformat(None)


def test_send_mpt_notification(mocker, mpt_client, order_factory, order_parameters_factory, buyer):
    mock_mpt_notify = mocker.patch(
        "swo_aws_extension.swo.notifications.mpt.notify", return_value=True
    )
    mock_get_rendered_template = mocker.patch(
        "swo_aws_extension.swo.notifications.mpt.get_rendered_template",
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
    mocker, mpt_client, order_factory, order_parameters_factory, buyer
):
    mock_mpt_notify = mocker.patch(
        "swo_aws_extension.swo.notifications.mpt.notify",
        side_effect=MPTHttpError(HTTPStatus.BAD_REQUEST, "Error"),
    )
    mocker.patch(
        "swo_aws_extension.swo.notifications.mpt.get_rendered_template",
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
