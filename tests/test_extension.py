import json
from http import HTTPStatus

from mpt_extension_sdk.core.events.dataclasses import Event
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.runtime.djapp.conf import get_for_product

from swo_aws_extension.extension import (
    ext,
    jwt_secret_callback,
    process_order_fulfillment,
)


def test_listener_registered():
    result = ext.events.get_listener("orders")

    assert result == process_order_fulfillment


def test_jwt_secret_callback(mocker, settings, mpt_client, webhook):
    mocked_webhook = mocker.patch(
        "swo_aws_extension.extension.get_webhook",
        return_value=webhook,
    )

    result = jwt_secret_callback(mpt_client, {"webhook_id": "WH-123-123"})

    assert result == get_for_product(settings, "WEBHOOKS_SECRETS", "PRD-1111-1111")
    mocked_webhook.assert_called_once_with(mpt_client, "WH-123-123")


def test_process_order_fulfillment(mocker):
    mocked_fulfill_order = mocker.patch(
        "swo_aws_extension.extension.fulfill_order",
    )
    client = mocker.MagicMock(spec=MPTClient)
    event = Event("evt-id", "orders", {"id": "ORD-0792-5000-2253-4210"})

    process_order_fulfillment(client, event)  # act

    mocked_fulfill_order.assert_called_once_with(client, event.data)


def test_process_order_validation(client, mocker, order_factory, jwt_token, webhook):
    mocker.patch(
        "swo_aws_extension.extension.get_webhook",
        return_value=webhook,
    )
    order = order_factory()

    result = client.post(
        "/api/v1/orders/validate",
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "X-Forwarded-Host": "aws.ext.s1.com",
        },
        data=json.dumps(order),
    )

    assert result.status_code == HTTPStatus.OK
    assert result.json() == order
