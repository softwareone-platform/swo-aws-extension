import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Annotated, Any

from django.conf import settings
from mpt_extension_sdk.core.extension import Extension
from mpt_extension_sdk.core.security import JWTAuth
from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_webhook
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError
from mpt_extension_sdk.runtime.djapp.conf import get_for_product
from ninja import Body

from swo_aws_extension.flows.fulfillment.base import fulfill_order
from swo_aws_extension.flows.order_utils import set_order_error
from swo_aws_extension.flows.validation.base import validate_order

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
    if order.get("type") == ORDER_TYPE_CHANGE:
        order = set_order_error(
            order,
            ValidationError(
                err_id="AWS003",
                message="Change orders are not supported by the AWS extension.",
            ).to_dict(),
        )
        return HTTPStatus.OK, order
    try:
        validated_order = validate_order(request.client, order)
    except Exception:
        logger.exception("Unexpected error during validation")
        return 400, {
            "id": "Unexpected error",
            "message": "Unexpected validation error - contact support.",
        }
    else:
        return HTTPStatus.OK, validated_order
