import logging
from collections.abc import Mapping
from typing import Annotated, Any

from django.conf import settings
from mpt_extension_sdk.core.extension import Extension
from mpt_extension_sdk.core.security import JWTAuth
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_webhook
from mpt_extension_sdk.runtime.djapp.conf import get_for_product
from ninja import Body

from swo_aws_extension.constants import HTTP_STATUS_BAD_REQUEST, HTTP_STATUS_OK
from swo_aws_extension.models import Error

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
    # TODO: Implement order fulfillment logic here
    logger.info("Received order fulfillment event: %s", event)


@ext.api.post(
    "/v1/orders/validate",
    response={
        HTTP_STATUS_OK: dict,
        HTTP_STATUS_BAD_REQUEST: Error,
    },
    auth=JWTAuth(jwt_secret_callback),
)
def process_order_validation(request, order: Annotated[dict | None, Body()] = None):
    """Start order process validation."""
    return HTTP_STATUS_OK, order
