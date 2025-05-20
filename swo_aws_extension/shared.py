from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.notifications import MPTNotifier

mpt_client = setup_client()
mpt_notifier = MPTNotifier(mpt_client)
