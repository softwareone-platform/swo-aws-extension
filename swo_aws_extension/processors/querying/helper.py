import datetime as dt

from swo_aws_extension.constants import OrderProcessingTemplateEnum
from swo_aws_extension.flows.order import PurchaseContext


def get_template_name(context: PurchaseContext) -> str:
    """Get order processing template name based on context."""
    if context.is_type_new_aws_environment():
        return OrderProcessingTemplateEnum.NEW_ACCOUNT
    return OrderProcessingTemplateEnum.EXISTING_ACCOUNT


def is_querying_timeout(context: PurchaseContext, querying_timeout_days: int) -> bool:
    """Check if order has been in querying more than timeout limit."""
    audit = context.order.get("audit", {})
    querying_at = audit.get("querying", {}).get("at")
    if not querying_at:
        return False
    querying_time = dt.datetime.fromisoformat(querying_at)
    if querying_time.tzinfo is None:
        querying_time = querying_time.replace(tzinfo=dt.UTC)
    now = dt.datetime.now(dt.UTC)
    return now - querying_time > dt.timedelta(days=querying_timeout_days)
