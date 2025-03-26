import logging
from pprint import pformat
from typing import Any, Mapping

from django.conf import settings
from ninja import Body
from swo.mpt.client import MPTClient
from swo.mpt.client.mpt import get_webhook
from swo.mpt.extensions.core import Extension, JWTAuth
from swo.mpt.extensions.runtime.djapp.conf import get_for_product

from swo_aws_extension.flows.fulfillment import fulfill_order
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.validation import validate_order
from swo_aws_extension.models import Error

logger = logging.getLogger(__name__)

ext = Extension()


def jwt_secret_callback(client: MPTClient, claims: Mapping[str, Any]) -> str:
    webhook = get_webhook(client, claims["webhook_id"])
    product_id = webhook["criteria"]["product.id"]
    return get_for_product(settings, "WEBHOOKS_SECRETS", product_id)


@ext.events.listener("orders")
def process_order_fulfillment(client, event):
    fulfill_order(client, event.data)


@ext.api.post(
    "/v1/orders/validate",
    response={
        200: dict,
        400: Error,
    },
    auth=JWTAuth(jwt_secret_callback),
)
def process_order_validation(request, order: dict = Body(None)):
    try:
        context = InitialAWSContext(order=order)
        validated_order = validate_order(request.client, context)
        logger.debug(f"Validated order: {pformat(validated_order)}")
        return 200, validated_order
    except Exception as e:
        logger.exception("Unexpected error during validation")
        return 400, Error(
            id="AWS001",
            message=f"Unexpected error during validation: {str(e)}.",
        )
