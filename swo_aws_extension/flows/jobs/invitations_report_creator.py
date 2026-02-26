import datetime as dt
import logging
from dataclasses import dataclass

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import _paginated, get_agreements_by_query  # noqa: PLC2701

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_customer_roles_deployed,
    get_responsibility_transfer_id,
    get_support_type,
)
from swo_aws_extension.swo.azure_blob_uploader import AzureBlobUploader
from swo_aws_extension.swo.excel_report_builder import ExcelReportBuilder
from swo_aws_extension.swo.notifications.teams import Button, TeamsNotificationManager
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)

ReportRow = list[str]
ReportRows = list[ReportRow]
ErrorMessages = list[str]

INVITATIONS_REPORT_HEADERS = (
    "PMA Account ID",
    "MPA Account ID",
    "Invitation ID",
    "Invitation Status",
    "Agreement ID",
    "Agreement Name",
    "Product ID",
    "Agreement Status",
    "Support Type",
    "Customer Roles Deployed",
    "Channel Handshake Approval Status",
    "Start Date",
    "End Date",
)


@dataclass
class ReportEntityData:
    """Data extracted from an agreement or order."""

    id: str = ""
    name: str = ""
    status: str = ""
    product_id: str = ""
    support_type: str = ""
    customer_roles_deployed: str = ""
    channel_handshake_approval_status: str = ""


# TODO: SDK candidate
def get_authorizations(
    mpt_client: MPTClient, rql_query: RQLQuery | None, limit: int = 10
) -> list[dict]:  # pragma: no cover
    """
    Retrieve authorizations based on the provided RQL query.

    Args:
        mpt_client (MPTClient): MPT API client instance.
        rql_query (RQLQuery): Query to filter authorizations.
        limit (int): Maximum number of authorizations to retrieve.

    Returns:
        list or None: List of authorizations or None if request fails.
    """
    url = (
        f"/catalog/authorizations?{rql_query}&select=externalIds,product"
        if rql_query
        else "/catalog/authorizations?select=externalIds,product"
    )
    return _paginated(mpt_client, url, limit=limit)


# TODO: SDK candidate
def get_orders_by_query(
    mpt_client: MPTClient, query: str, limit: int = 10
) -> list[dict]:  # pragma: no cover
    """
    This method is used to get the orders by query.

    Args:
        mpt_client (MPTClient): MPT API client instance.
        query (str): Query to filter orders.
        limit (int): Maximum number of orders to retrieve.

    Returns:
        list[dict]: List of orders.
    """
    url = f"/commerce/orders?{query}"
    return _paginated(mpt_client, url, limit=limit)


class InvitationsReportCreator:
    """Create invitations report."""

    def __init__(self, mpt_client: MPTClient, product_ids: list[str], config: Config):
        """Initialize InvitationsReportCreator.

        Args:
            mpt_client: MPT API client instance.
            product_ids: List of product IDs to filter authorizations.
            config: Config object
        """
        self.mpt_client = mpt_client
        self.product_ids = product_ids
        self.config = config
        self.notifier = TeamsNotificationManager()
        self.excel_builder = ExcelReportBuilder(list(INVITATIONS_REPORT_HEADERS))
        self.blob_uploader = AzureBlobUploader(
            connection_string=self.config.azure_storage_connection_string,
            container_name=self.config.azure_storage_container,
            sas_expiry_days=self.config.azure_storage_sas_expiry_days,
        )

    def create_and_notify_teams(self) -> None:
        """Create invitations report, upload to Azure Storage and notify via Teams.

        The Excel is built in memory, uploaded to Azure Blob Storage and a Teams
        notification with a download link (SAS URL valid for a configured period of time) is sent.
        """
        logger.info("Creating invitations report for Teams notification...")

        authorizations = get_authorizations(
            self.mpt_client, RQLQuery(product__id__in=self.product_ids), 10
        )

        rows, errors = self._process_authorizations_into_rows(authorizations)
        if errors:
            error_message = "\n".join(errors)
            self.notifier.send_error(
                "Error getting AWS invitations",
                f"Errors occurred while fetching AWS invitations:\n{error_message}",
            )

        download_url = self._upload_report(rows)
        self.notifier.send_success(
            "AWS Billing Transfer Invitations Report",
            f"The report has been generated with **{len(rows)}** agreement(s).",
            button=Button(label="Download report", url=download_url),
        )
        logger.info("Invitations report uploaded and Teams notification sent.")

    def _upload_report(self, rows: ReportRows) -> str:
        excel_bytes = self.excel_builder.build_from_rows(rows)
        date_str = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
        report_folder = self.config.report_invitations_folder
        blob_name = f"{report_folder}{date_str}.xlsx"
        return self.blob_uploader.upload_and_get_sas_url(excel_bytes, blob_name)

    def _process_authorizations_into_rows(
        self, authorizations: list[dict]
    ) -> tuple[ReportRows, ErrorMessages]:
        """Process authorizations into report rows and collect errors."""
        rows: ReportRows = []
        errors: ErrorMessages = []

        for authorization in authorizations:
            auth_rows, auth_error = self._process_single_authorization(authorization)
            rows.extend(auth_rows)
            if auth_error:
                errors.append(auth_error)

        return rows, errors

    def _process_single_authorization(self, authorization: dict) -> tuple[ReportRows, str | None]:
        """Process a single authorization and return rows and optional error."""
        try:
            aws_client = AWSClient(
                self.config,
                authorization["externalIds"]["operations"],
                self.config.management_role_name,
            )
        except AWSError as error:
            logger.warning(
                "Error getting AWS invitations for authorization %s: %s",
                authorization["id"],
                error,
            )
            return [], f"Authorization {authorization['id']}: {error}"

        return self._build_rows_from_authorization(authorization, aws_client), None

    def _build_rows_from_authorization(
        self, authorization: dict, aws_client: AWSClient
    ) -> ReportRows:
        """Build report rows from authorization data."""
        aws_invitations = aws_client.get_inbound_responsibility_transfers()
        processed_data = self._get_processed_data(authorization)

        return [
            self._invitation_to_row(invitation, processed_data) for invitation in aws_invitations
        ]

    def _get_processed_data(self, authorization: dict) -> dict[str, ReportEntityData]:
        """Get processed data combining agreements and orders."""
        agreements = self._get_agreements(authorization)
        invitation_agreements = self._process_entities(agreements)

        mpt_orders = self._get_orders(authorization)
        filtered_orders = [
            order
            for order in mpt_orders
            if get_responsibility_transfer_id(order) not in invitation_agreements
        ]
        invitation_orders = self._process_entities(filtered_orders, is_order=True)

        return invitation_agreements | invitation_orders

    def _get_agreements(self, authorization: dict) -> list[dict]:
        select = "&select=parameters,authorization.externalIds.operations"
        rql_filter = RQLQuery(authorization__id__eq=authorization["id"]) & RQLQuery(
            status__ne="Draft"
        )
        query_str = f"{rql_filter}{select}"
        return get_agreements_by_query(self.mpt_client, query_str, limit=100)

    def _get_orders(self, authorization: dict) -> list[dict]:
        select = "&select=parameters,authorization.externalIds.operations"
        rql_filter = (
            RQLQuery(authorization__id__eq=authorization["id"])
            & RQLQuery(product__id__in=self.product_ids)
            & RQLQuery().status.out([
                "Completed",
                "Draft",
            ])
        )
        query_str = f"{rql_filter}{select}"
        return get_orders_by_query(self.mpt_client, query_str, limit=100)

    def _invitation_to_row(
        self, invitation: dict, mpt_data: dict[str, ReportEntityData]
    ) -> list[str]:
        start_date = (
            invitation.get("StartTimestamp").strftime("%Y-%m-%d")
            if invitation.get("StartTimestamp")
            else ""
        )
        end_date = (
            invitation.get("EndTimestamp").strftime("%Y-%m-%d")
            if invitation.get("EndTimestamp")
            else ""
        )
        mpt_item_data = mpt_data.get(invitation.get("Id"), ReportEntityData())
        return [
            invitation.get("Target", {}).get("ManagementAccountId", ""),
            invitation.get("Source", {}).get("ManagementAccountId", ""),
            invitation.get("Id", ""),
            invitation.get("Status", ""),
            mpt_item_data.id,
            mpt_item_data.name,
            mpt_item_data.product_id,
            mpt_item_data.status,
            mpt_item_data.support_type,
            mpt_item_data.customer_roles_deployed,
            mpt_item_data.channel_handshake_approval_status,
            start_date,
            end_date,
        ]

    def _extract_entity_data(self, entity: dict, *, is_order: bool = False) -> ReportEntityData:
        source = entity.get("agreement", {}) if is_order else entity
        return ReportEntityData(
            id=source.get("id", ""),
            name=source.get("name", ""),
            status=source.get("status", ""),
            product_id=entity.get("product", {}).get("id", ""),
            support_type=get_support_type(entity) or "",
            customer_roles_deployed=(get_customer_roles_deployed(entity) or "").capitalize(),
            channel_handshake_approval_status=(
                get_channel_handshake_approval_status(entity) or ""
            ).capitalize(),
        )

    def _process_entities(
        self, entities: list[dict], *, is_order: bool = False
    ) -> dict[str, ReportEntityData]:
        processed_data: dict[str, ReportEntityData] = {}

        for entity in entities:
            invitation_id = get_responsibility_transfer_id(entity)
            if not invitation_id:
                continue

            processed_data[invitation_id] = self._extract_entity_data(entity, is_order=is_order)

        return processed_data
