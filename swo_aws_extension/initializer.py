import os

os.environ.setdefault("MPT_INITIALIZER", "swo_aws_extension.initializer.initialize")
from mpt_extension_sdk.constants import (
    DEFAULT_APP_CONFIG_GROUP,
    DEFAULT_APP_CONFIG_NAME,
)
from mpt_extension_sdk.runtime.initializer import initialize as sdk_initialize
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor


def initialize(options, group=DEFAULT_APP_CONFIG_GROUP, name=DEFAULT_APP_CONFIG_NAME):
    """Custom initializaer of extension."""
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

    django.setup()
