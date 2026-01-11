import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Annotated, Any

from django.conf import settings
from mpt_extension_sdk.core.extension import Extension
from mpt_extension_sdk.core.security import JWTAuth
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_webhook
from mpt_extension_sdk.runtime.djapp.conf import get_for_product
from ninja import Body

from swo_aws_extension.flows.fulfillment.base import fulfill_order
from swo_aws_extension.parameters import update_parameters_visibility

logger = logging.getLogger(__name__)

ext = Extension()


def jwt_secret_callback(client: MPTClient, claims: Mapping[str, Any]) -> str:
    """JWT callback."""
    webhook = get_webhook(client, claims["webhook_id"])
    product_id = webhook["criteria"]["product.id"]
    return get_for_product(settings, "WEBHOOKS_SECRETS", product_id)


@ext.events.listener("orders")
def process_order_fulfillment(client, event):
    """Process order fulfillment."""
    fulfill_order(client, event.data)


@ext.api.post(
    "/v1/orders/validate",
    response={
        HTTPStatus.OK: dict,
        HTTPStatus.BAD_REQUEST: dict,
    },
    auth=JWTAuth(jwt_secret_callback),
)
def process_order_validation(request, order: Annotated[dict, Body()]):
    """Start order process validation."""
    try:
        validated_order = update_parameters_visibility(order)
    except Exception:
        logger.exception("Unexpected error during validation")
        return 400, {
            "id": "Unexpected error",
            "message": "Unexpected validation error - contact support.",
        }
    else:
        return HTTPStatus.OK, validated_order
