import datetime as dt
import logging
from collections.abc import Callable

import boto3
from botocore.exceptions import ClientError

from swo_aws_extension.aws.constants import DEFAULT_BILLING_EXPORT_QUERY_STATEMENT
from swo_aws_extension.aws.errors import (
    AWSError,
    InvalidDateInTerminateResponsibilityError,
    wrap_boto3_error,
)
from swo_aws_extension.config import Config
from swo_aws_extension.swo.openid.client import OpenIDClient

MINIMUM_DAYS_MONTH = 28
MAX_RESULTS_PER_PAGE = 100


logger = logging.getLogger(__name__)


def get_paged_response(
    method_to_call: Callable,
    data_key: str,
    kwargs: dict | None = None,
    # NextToken (PascalCase) for most AWS APIs, nextToken (camelCase) for Partner Central
    pagination_key: str = "NextToken",
) -> list:
    """Retrieves paginated data from API."""
    response_data, next_token = _get_response(method_to_call, kwargs, data_key, pagination_key)
    while next_token:
        r_data, next_token = _get_response(
            method_to_call, kwargs, data_key, pagination_key, next_token
        )
        response_data.extend(r_data)

    return response_data


def _get_response(
    method_to_call: Callable,
    kwargs: dict,
    data_key: str,
    pagination_key: str = "NextToken",
    next_token: str = "",
) -> tuple[list, str | None]:
    call_args = dict(kwargs or {})
    if next_token:
        call_args[pagination_key] = next_token
    response = method_to_call(**call_args)

    return response.get(data_key, []), response.get(pagination_key)


class AWSClient:
    """AWS client."""

    # TODO: Remove logic to get and validate credentials in the init method
    def __init__(self, config: Config, account_id: str, role_name: str) -> None:
        """
        Initialize the AWS client.

        Args:
            config: Configuration object containing AWS and CCP settings
            account_id: The AWS account ID to assume the role in.
            role_name: The name of the IAM role to assume.
        """
        self.config = config
        self.account_id = account_id
        self.role_name = role_name
        self._openid_client = OpenIDClient(config)
        self.credentials = self._get_credentials()
        self._validate_credentials()

    @wrap_boto3_error
    def get_inbound_responsibility_transfers(self) -> list:
        """
        Retrieves a list of inbound responsibility transfers.

        Raises:
            botocore.exceptions.ClientError
        """
        return get_paged_response(
            self._get_organization_client().list_inbound_responsibility_transfers,
            "ResponsibilityTransfers",
            {"Type": "BILLING", "MaxResults": MAX_RESULTS_PER_PAGE},
        )

    @wrap_boto3_error
    def terminate_responsibility_transfer(
        self, transfer_id: str, end_timestamp: dt.datetime
    ) -> dict:
        """Terminates a responsibility transfer."""
        client = self._get_organization_client()
        try:
            return client.terminate_responsibility_transfer(
                Id=transfer_id, EndTimestamp=end_timestamp
            )
        except client.exceptions.InvalidInputException as exception:
            reason = exception.response.get("Reason", "")
            message = exception.response.get("Message", "")
            if reason == "INVALID_END_DATE":
                raise InvalidDateInTerminateResponsibilityError(
                    message, end_timestamp
                ) from exception
            raise

    @wrap_boto3_error
    def invite_organization_to_transfer_billing(
        self, customer_id: str, start_timestamp: int, source_name: str
    ) -> dict:
        """Invite organization to transfer billing responsibility."""
        org_client = self._get_organization_client()
        return org_client.invite_organization_to_transfer_responsibility(
            Type="BILLING",
            Target={"Id": customer_id, "Type": "ACCOUNT"},
            StartTimestamp=start_timestamp,
            SourceName=source_name,
        )

    @wrap_boto3_error
    def get_responsibility_transfer_details(self, transfer_id: str) -> dict:
        """Describe responsibility transfer."""
        org_client = self._get_organization_client()
        return org_client.describe_responsibility_transfer(Id=transfer_id)

    @wrap_boto3_error
    def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        group_by: list[dict] | None = None,
        filter_by: dict | None = None,
        view_arn: str | None = None,
    ) -> list[dict]:
        """Get cost and usage data for the specified date range."""
        kwarg: dict = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "MONTHLY",
            "Metrics": ["UnblendedCost"],
        }
        if group_by:
            kwarg["GroupBy"] = group_by
        if filter_by:
            kwarg["Filter"] = filter_by
        if view_arn:
            kwarg["BillingViewArn"] = view_arn
        return get_paged_response(
            self._get_cost_explorer_client().get_cost_and_usage,
            "ResultsByTime",
            kwarg,
        )

    @wrap_boto3_error
    def get_current_billing_view_by_account_id(self, account_id: str) -> list[dict]:
        """Get billing views by account ID for the current month.

        Args:
            account_id: The AWS account ID.

        Returns:
            List of billing views for the current month.
        """
        today = dt.datetime.now(dt.UTC).date()
        first_day = today.replace(day=1)
        next_month = today.replace(day=MINIMUM_DAYS_MONTH) + dt.timedelta(days=4)
        last_day = next_month.replace(day=1) - dt.timedelta(days=1)
        return self.get_billing_views_by_account_id(
            account_id=account_id, start_date=first_day.isoformat(), end_date=last_day.isoformat()
        )

    @wrap_boto3_error
    def get_billing_views_by_account_id(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Get billing views by account ID for a date range.

        Args:
            account_id: The AWS account ID.
            start_date: Start date in YYYY-MM-DD format (first day of month).
            end_date: End date in YYYY-MM-DD format (last day of month).

        Returns:
            List of billing views for the date range.
        """
        billing_client = self._get_billing_client()
        first_day = dt.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=dt.UTC)
        end_datetime = dt.datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=dt.UTC)
        last_day = dt.datetime.combine(
            end_datetime.date(),
            dt.time.max,
            tzinfo=dt.UTC,
        )

        return get_paged_response(
            billing_client.list_billing_views,
            "billingViews",
            {
                "billingViewTypes": ["BILLING_TRANSFER"],
                "sourceAccountId": account_id,
                "maxResults": MAX_RESULTS_PER_PAGE,
                "activeTimeRange": {
                    "activeAfterInclusive": first_day,
                    "activeBeforeInclusive": last_day,
                },
            },
            pagination_key="nextToken",
        )

    @wrap_boto3_error
    def create_billing_group(
        self, responsibility_transfer_arn: str, pricing_plan_arn: str, name: str, description: str
    ) -> dict:
        """Create a billing group."""
        billing_conductor_client = self._get_billing_conductor_client()
        return billing_conductor_client.create_billing_group(
            Name=name,
            Description=description,
            ComputationPreference={"PricingPlanArn": pricing_plan_arn},
            AccountGrouping={
                "ResponsibilityTransferArn": responsibility_transfer_arn,
            },
        )

    @wrap_boto3_error
    def delete_billing_group(self, billing_group_arn: str) -> dict:
        """Delete a billing group."""
        billing_conductor_client = self._get_billing_conductor_client()
        return billing_conductor_client.delete_billing_group(
            Arn=billing_group_arn,
        )

    @wrap_boto3_error
    def get_program_management_id_by_account(self, account_id) -> str:
        """Get Program Management Account Identifier by account ID."""
        partner_central_client = self._get_partner_central_client()
        response = partner_central_client.list_program_management_accounts(
            catalog="AWS", accountIds=[account_id]
        )
        program_management_accounts = response.get("items", [])
        return program_management_accounts[0].get("id", "") if program_management_accounts else ""

    @wrap_boto3_error
    def create_relationship_in_partner_central(
        self,
        pma_identifier: str,
        mpa_id: str,
        scu: str,
    ) -> dict:
        """Create relationship in Partner Central."""
        partner_central_client = self._get_partner_central_client()
        return partner_central_client.create_relationship(
            catalog="AWS",
            associationType="END_CUSTOMER",
            programManagementAccountIdentifier=pma_identifier,
            associatedAccountId=mpa_id,
            displayName=f"{scu}-{mpa_id}",
            resaleAccountModel="END_CUSTOMER",
            sector="COMMERCIAL",
        )

    @wrap_boto3_error
    def create_channel_handshake(
        self,
        pma_identifier: str,
        relationship_identifier: str,
        end_date: dt.datetime,
        note: str,
    ) -> dict:
        """Create channel handshake in Partner Central."""
        partner_central_client = self._get_partner_central_client()
        return partner_central_client.create_channel_handshake(
            handshakeType="START_SERVICE_PERIOD",
            catalog="AWS",
            associatedResourceIdentifier=relationship_identifier,
            payload={
                "startServicePeriodPayload": {
                    "programManagementAccountIdentifier": pma_identifier,
                    "note": note,
                    "servicePeriodType": "FIXED_COMMITMENT_PERIOD",
                    "endDate": end_date,
                }
            },
        )

    @wrap_boto3_error
    def delete_pc_relationship(self, pm_identifier: str, relationship_id: str):
        """Delete relationship in Partner Central."""
        partner_central_client = self._get_partner_central_client()
        return partner_central_client.delete_relationship(
            catalog="AWS",
            identifier=relationship_id,
            programManagementAccountIdentifier=pm_identifier,
        )

    @wrap_boto3_error
    def get_channel_handshakes_by_resource(
        self,
        resource_identifier: str,
    ) -> list[dict]:
        """Get channel handshakes by resource identifier in Partner Central."""
        return get_paged_response(
            self._get_partner_central_client().list_channel_handshakes,
            "items",
            {
                "catalog": "AWS",
                "participantType": "SENDER",
                "handshakeType": "START_SERVICE_PERIOD",
                "associatedResourceIdentifiers": [resource_identifier],
                "maxResults": MAX_RESULTS_PER_PAGE,
            },
            pagination_key="nextToken",
        )

    def get_channel_handshake_by_id(
        self, resource_identifier: str, handshake_id: str
    ) -> dict | None:
        """Get channel handshake by ID."""
        handshakes = self.get_channel_handshakes_by_resource(
            resource_identifier=resource_identifier
        )
        return next((hs for hs in handshakes if hs.get("id") == handshake_id), None)

    @wrap_boto3_error
    def list_invoice_summaries_by_account_id(
        self, account_id: str, year: int, month: int
    ) -> list[dict]:
        """List invoice summaries for the specified date range.

        Args:
            account_id: The AWS account ID for which to list invoice summaries.
            year: The year of the billing period.
            month: The month of the billing period (1-12).

        Returns:
            A list of invoice summaries for the specified account and billing period.
        """
        return get_paged_response(
            self._get_invoicing_client().list_invoice_summaries,
            "InvoiceSummaries",
            {
                "Selector": {"ResourceType": "ACCOUNT_ID", "Value": account_id},
                "Filter": {"BillingPeriod": {"Month": month, "Year": year}},
            },
        )

    def create_s3_bucket(self, bucket_name: str, region: str) -> None:
        """Create an S3 bucket in the given region, ignoring it if already owned.

        Args:
            bucket_name: Name of the S3 bucket to create.
            region: AWS region where the bucket will be created.

        Raises:
            AWSError: If the bucket creation fails for any reason other than it already being
                owned by this account.
        """
        try:
            self._create_s3_bucket(bucket_name, region)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
                logger.info(
                    "S3 bucket %s already exists and is owned by this account.", bucket_name
                )
                return
            raise AWSError(f"Failed to create S3 bucket {bucket_name}: {exc}") from exc
        except Exception as exc:
            raise AWSError(f"Unexpected error creating S3 bucket {bucket_name}: {exc}") from exc

    def _create_s3_bucket(self, bucket_name: str, region: str) -> None:
        s3_client = self._get_s3_client()
        create_kwargs: dict = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3_client.create_bucket(**create_kwargs)

    @wrap_boto3_error
    def create_billing_export(
        self,
        billing_view_arn: str,
        export_name: str,
        s3_bucket: str,
        s3_prefix: str,
        region: str = "us-east-1",
    ) -> str:
        """Create a CUR2 export for a billing transfer view.

        Args:
            billing_view_arn: ARN of the BILLING_TRANSFER view to export.
            export_name: Name for the export (must be unique per account).
            s3_bucket: Destination S3 bucket name.
            s3_prefix: Destination S3 key prefix.
            region: AWS region for the S3 destination and BCM client.

        Returns:
            The ARN of the created export.
        """
        bcm_client = self._get_bcm_data_exports_client()
        response = bcm_client.create_export(
            Export={
                "Name": export_name,
                "DataQuery": {
                    "QueryStatement": DEFAULT_BILLING_EXPORT_QUERY_STATEMENT,
                    "TableConfigurations": {
                        "COST_AND_USAGE_REPORT": {
                            "TIME_GRANULARITY": "HOURLY",
                            "INCLUDE_RESOURCES": "FALSE",
                            "INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY": "FALSE",
                            "INCLUDE_SPLIT_COST_ALLOCATION_DATA": "FALSE",
                            "BILLING_VIEW_ARN": billing_view_arn,
                        }
                    },
                },
                "DestinationConfigurations": {
                    "S3Destination": {
                        "S3Bucket": s3_bucket,
                        "S3Prefix": s3_prefix,
                        "S3Region": region,
                        "S3OutputConfigurations": {
                            "OutputType": "CUSTOM",
                            "Format": "PARQUET",
                            "Compression": "PARQUET",
                            "Overwrite": "OVERWRITE_REPORT",
                        },
                    }
                },
                "RefreshCadence": {
                    "Frequency": "SYNCHRONOUS",
                },
            }
        )
        return str(response.get("ExportArn", ""))

    @wrap_boto3_error
    def list_s3_objects(self, bucket: str, prefix: str) -> list[str]:
        """List all S3 object keys under the given bucket and prefix.

        Args:
            bucket: The S3 bucket name.
            prefix: The S3 key prefix to filter by.

        Returns:
            List of S3 object keys matching the prefix.
        """
        paginator = self._get_s3_client().get_paginator("list_objects_v2")
        return [
            s3_item.get("Key", "")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix)
            for s3_item in page.get("Contents", [])
            if s3_item.get("Key", "")
        ]

    @wrap_boto3_error
    def download_s3_object(self, bucket: str, key: str) -> bytes:
        """Download an S3 object and return its content as bytes.

        Args:
            bucket: The S3 bucket name.
            key: The S3 object key.

        Returns:
            The raw content of the S3 object.
        """
        s3_client = self._get_s3_client()
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    @wrap_boto3_error
    def list_existing_billing_exports(self, s3_bucket: str, s3_prefix: str) -> set[str]:
        """Return the set of billing-view ARNs that already have CUR2 exports.

        Inspects all existing BCM exports and returns those whose destination
        matches the given bucket/prefix and whose query targets a BILLING_TRANSFER view.

        Args:
            s3_bucket: S3 bucket name to filter by.
            s3_prefix: S3 prefix to filter by (checked with ``in``).

        Returns:
            Set of billing-view ARNs that already have an export configured.
        """
        bcm_client = self._get_bcm_data_exports_client()
        export_arns = [
            summary.get("ExportArn", "")
            for summary in get_paged_response(bcm_client.list_exports, "Exports")
            if summary.get("ExportArn")
        ]
        return self._collect_matching_export_arns(bcm_client, export_arns, s3_bucket, s3_prefix)

    def _collect_matching_export_arns(
        self,
        bcm_client,
        export_arns: list[str],
        s3_bucket: str,
        s3_prefix: str,
    ) -> set[str]:
        """Collect billing-view ARNs from exports that match the given bucket and prefix."""
        existing_arns: set[str] = set()
        for export_arn in export_arns:
            billing_view_arn = self._get_billing_view_arn_from_export(
                bcm_client, export_arn, s3_bucket, s3_prefix
            )
            if billing_view_arn:
                existing_arns.add(billing_view_arn)
        return existing_arns

    def _get_billing_view_arn_from_export(
        self,
        bcm_client,
        export_arn: str,
        s3_bucket: str,
        s3_prefix: str,
    ) -> str:
        """Return the billing-view ARN of an export if it matches bucket/prefix, or empty string.

        Args:
            bcm_client: The BCM Data Exports client.
            export_arn: The ARN of the export to inspect.
            s3_bucket: The S3 bucket name to match against.
            s3_prefix: The S3 key prefix to match against.

        Returns:
            The billing-view ARN if the export matches the bucket/prefix, otherwise empty string.

        Raises:
            AWSError: If the export details cannot be retrieved from BCM.
        """
        try:
            detail = bcm_client.get_export(ExportArn=export_arn).get("Export", {})
        except ClientError as exc:
            raise AWSError(f"Failed to retrieve export details for {export_arn}: {exc}") from exc
        except Exception as exc:
            raise AWSError(
                f"Unexpected error retrieving export details for {export_arn}: {exc}"
            ) from exc
        dest = detail.get("DestinationConfigurations", {}).get("S3Destination", {})
        if dest.get("S3Bucket") != s3_bucket:
            return ""
        if s3_prefix not in dest.get("S3Prefix", ""):
            return ""
        table_config = detail.get("DataQuery", {}).get("TableConfigurations", {})
        billing_view_arn = table_config.get("COST_AND_USAGE_REPORT", {}).get("BILLING_VIEW_ARN", "")
        if billing_view_arn and "billing-transfer" in billing_view_arn:
            return billing_view_arn
        return ""

    @wrap_boto3_error
    def _get_credentials(self):
        if not self.account_id:
            raise AWSError("Parameter 'account_id' must be provided to assume the role.")

        role_arn = f"arn:aws:iam::{self.account_id}:role/{self.role_name}"
        response = boto3.client("sts").assume_role_with_web_identity(
            RoleArn=role_arn,
            RoleSessionName="SWOExtensionOnboardingSession",
            WebIdentityToken=self._openid_client.fetch_access_token(self.config.aws_openid_scope),
        )
        return response["Credentials"]

    @wrap_boto3_error
    def _validate_credentials(self):
        """Method used to validate credentials."""
        sts_client = self._get_sts_client()
        return sts_client.get_caller_identity()

    def _get_organization_client(self):
        return self._get_client("organizations")

    def _get_client(self, service_name):
        return boto3.client(
            service_name,
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
        )

    def _get_sts_client(self):
        return boto3.client(
            "sts",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
        )

    def _get_cost_explorer_client(self):
        """
        Get the Cost Explorer client.

        Returns:
            The Cost Explorer client.
        """
        return boto3.client(
            "ce",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name="us-east-1",
        )

    def _get_billing_client(self):
        """
        Get the Billing client.

        Returns:
            The Billing client.
        """
        return boto3.client(
            "billing",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name="us-east-1",
        )

    def _get_billing_conductor_client(self):
        """
        Get the Billing Conductor client.

        Returns:
            The Billing Conductor client.
        """
        return boto3.client(
            "billingconductor",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
        )

    def _get_partner_central_client(self):
        """
        Get the Partner Central Channel client.

        Returns:
            The Partner Central Channel client.
        """
        return boto3.client(
            "partnercentral-channel",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name="us-east-1",
        )

    def _get_s3_client(self):
        """Get the S3 client.

        Returns:
            The S3 client.
        """
        return self._get_client("s3")

    def _get_bcm_data_exports_client(self):
        """Get the BCM Data Exports client.

        Returns:
            The BCM Data Exports client.
        """
        return self._get_client_in_region("bcm-data-exports", "us-east-1")

    def _get_invoicing_client(self):
        """Get the Invoicing client.

        Returns:
            The Invoicing client.
        """
        return self._get_client_in_region("invoicing", "us-east-1")

    def _get_client_in_region(self, service_name: str, region_name: str):
        """Get a boto3 client for the given service and region using session credentials.

        Args:
            service_name: The AWS service name (e.g. ``"billing"``).
            region_name: The AWS region (e.g. ``"us-east-1"``).

        Returns:
            A boto3 client configured with the current session credentials.
        """
        return boto3.client(
            service_name,
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name=region_name,
        )
