import logging

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.parameters import get_mpa_account_id, get_order_account_email, get_phase
from swo_aws_extension.swo.mpt.order import get_orders_by_query
from swo_aws_extension.swo.rql.query_builder import RQLQuery
from swo_aws_extension.utils import date_parser

logger = logging.getLogger(__name__)


ReportRow = list[str]
ReportRows = list[ReportRow]
ErrorMessages = list[str]

PENDING_ORDERS_INFORMATION_REPORT_HEADERS = (
    "ID",
    "Order Type",
    "status",
    "Creation Date",
    "Last update",
    "Product",
    "Client ID",
    "Client Name",
    "Seller",
    "Fulfillment Phase",
    "Master Payer ID",
    "Order Account Email",
    "Created By",
    "Assignee",
)


class PendingOrdersInformationReportCreator:
    """Create pending orders information report."""

    def __init__(self, mpt_client: MPTClient):
        """Initialize PendingOrdersInformationReportCreator.

        Args:
            mpt_client: MPTClient instance to interact with MPT API.
        """
        self.mpt_client = mpt_client

    def create(self) -> ReportRows:
        """Create pending orders information report and return its path.

        Returns:
            Path of the created report.
        """
        logger.info("Creating pending orders information report...")

        pending_orders = self._get_pending_orders()

        return self._process_orders_into_rows(pending_orders)

    def _process_orders_into_rows(self, orders: list[dict]) -> ReportRows:
        """Process orders information into report rows.

        Args:
            orders: List of orders information as returned by MPT API.

        Returns:
            A list of report rows.
        """
        return [self._order_to_row(order) for order in orders]

    def _order_to_row(self, order: dict) -> list[str]:  # noqa: WPS210
        """Convert order information into a report row.

        Args:
            order: Order information as returned by MPT API.

        Returns:
            A report row built from the order information.
        """
        fulfillment_phase = get_phase(order)
        mpa_account_id = get_mpa_account_id(order)
        order_account_email = get_order_account_email(order)
        audit_info = order.get("audit", {})
        created = audit_info.get("created") or {}
        updated = audit_info.get("updated") or {}
        created_by = created.get("by") or {}
        return [
            order.get("id", ""),
            order.get("type", ""),
            order.get("status", ""),
            date_parser.to_str(created.get("at", "")),
            date_parser.to_str(updated.get("at", "")),
            order.get("product", {}).get("name", ""),
            order.get("client", {}).get("id", ""),
            order.get("client", {}).get("name", ""),
            order.get("seller", {}).get("name", ""),
            fulfillment_phase,
            mpa_account_id,
            order_account_email,
            created_by.get("name", ""),
            order.get("assignee", {}).get("name", ""),
        ]

    def _get_pending_orders(self) -> list[dict]:
        """Get pending orders information from MPT API.

        Returns:
            List of orders information as returned by MPT API.
        """
        select = "&select=audit,parameters"
        report_statuses = ["Querying", "Processing"]
        rql_filter = RQLQuery(status__in=report_statuses)
        query_str = f"{rql_filter}{select}"
        return get_orders_by_query(self.mpt_client, query_str, limit=100)
