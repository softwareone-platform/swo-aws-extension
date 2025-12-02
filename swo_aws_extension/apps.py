from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from swo.mpt.extensions.runtime.djapp.apps import DjAppConfig

from .extension import ext


class ExtensionConfig(DjAppConfig):
    name = "swo_aws_extension"
    verbose_name = "SWO AWS Extension"
    extension = ext

    def extension_ready(self):
        error_msgs = []

        if len(settings.MPT_PRODUCTS_IDS) > 1:
            error_msgs.append(
                "Multiple product IDs are not supported. Please configure only one AWS product ID."
            )

        product_id = settings.AWS_PRODUCT_ID

        if (
            "WEBHOOKS_SECRETS" not in settings.EXTENSION_CONFIG
            or product_id not in settings.EXTENSION_CONFIG["WEBHOOKS_SECRETS"]
        ):
            msg = (
                f"The webhook secret for {product_id} is not found. "
                f"Please, specify it in EXT_WEBHOOKS_SECRETS environment variable."
            )
            error_msgs.append(msg)

        if error_msgs:
            raise ImproperlyConfigured("\n".join(error_msgs))
