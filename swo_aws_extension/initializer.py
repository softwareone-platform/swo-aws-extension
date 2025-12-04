import os

os.environ.setdefault("MPT_INITIALIZER", "swo_aws_extension.initializer.initialize")
from mpt_extension_sdk.constants import (
    DEFAULT_APP_CONFIG_GROUP,
    DEFAULT_APP_CONFIG_NAME,
)
from mpt_extension_sdk.runtime.initializer import initialize as sdk_initialize
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor


def initialize(options, group=DEFAULT_APP_CONFIG_GROUP, name=DEFAULT_APP_CONFIG_NAME):
    """Custom initializer of extension."""
    options["django_settings_module"] = "swo_aws_extension.default"

    sdk_initialize(
        options=options,
        group=group,
        name=name,
    )

    import django  # noqa: PLC0415
    from django.conf import settings  # noqa: PLC0415

    if settings.USE_APPLICATIONINSIGHTS:
        BotocoreInstrumentor().instrument()

    # By default, MPT_PRODUCT_IDS is configured to support multiple products. However,
    # this extension only supports a single AWS product. Therefore, we set AWS_PRODUCT_ID
    # to the first product ID in the list.
    settings.AWS_PRODUCT_ID = settings.MPT_PRODUCTS_IDS[0] if settings.MPT_PRODUCTS_IDS else None
    django.setup()
