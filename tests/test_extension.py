import json

from mpt_extension_sdk.core.events.dataclasses import Event
from mpt_extension_sdk.runtime.djapp.conf import get_for_product

from swo_aws_extension.extension import (
    ext,
    jwt_secret_callback,
    process_order_fulfillment,
)
from swo_aws_extension.flows.order import InitialAWSContext


def test_listener_registered():
    assert ext.events.get_listener("orders") == process_order_fulfillment


def test_process_order_fulfillment(mocker):
    mocked_fulfill_order = mocker.patch(
        "swo_aws_extension.extension.fulfill_order",
    )

    client = mocker.MagicMock()
    event = Event("evt-id", "orders", {"id": "ORD-0792-5000-2253-4210"})

    process_order_fulfillment(client, event)

    mocked_fulfill_order.assert_called_once_with(client, event.data)


def test_jwt_secret_callback(mocker, settings, mpt_client, webhook):
    mocked_webhook = mocker.patch(
        "swo_aws_extension.extension.get_webhook",
        return_value=webhook,
    )
    assert jwt_secret_callback(mpt_client, {"webhook_id": "WH-123-123"}) == get_for_product(
        settings, "WEBHOOKS_SECRETS", "PRD-1111-1111"
    )
    mocked_webhook.assert_called_once_with(mpt_client, "WH-123-123")


def test_process_order_validation(client, mocker, order_factory, jwt_token, webhook):
    mocker.patch(
        "swo_aws_extension.extension.get_webhook",
        return_value=webhook,
    )
    order = order_factory()
    m_validate = mocker.patch("swo_aws_extension.extension.validate_order", return_value=order)
    resp = client.post(
        "/api/v1/orders/validate",
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "X-Forwarded-Host": "aws.ext.s1.com",
        },
        data=json.dumps(order),
    )
    assert resp.status_code == 200
    assert resp.json() == order
    context = InitialAWSContext.from_order_data(order)
    m_validate.assert_called_once_with(mocker.ANY, context)


def test_process_order_validation_error(client, mocker, jwt_token, webhook):
    mocker.patch(
        "swo_aws_extension.extension.get_webhook",
        return_value=webhook,
    )
    mocker.patch(
        "swo_aws_extension.extension.validate_order",
        side_effect=Exception("A super duper error"),
    )
    resp = client.post(
        "/api/v1/orders/validate",
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "X-Forwarded-Host": "aws.ext.s1.com",
        },
        data={"whatever": "order"},
    )
    assert resp.status_code == 400
    assert resp.json() == {
        "id": "AWS001",
        "message": "Unexpected error during validation: A super duper error.",
    }
