import datetime as dt
import logging
from collections.abc import Callable

import boto3

from swo_aws_extension.aws.errors import (
    AWSError,
    wrap_boto3_error,
)
from swo_aws_extension.config import Config
from swo_aws_extension.swo.openid.client import OpenIDClient

MINIMUM_DAYS_MONTH = 28
MAX_RESULTS_PER_PAGE = 20

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
        return self._get_organization_client().terminate_responsibility_transfer(
            Id=transfer_id, EndTimestamp=end_timestamp
        )

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
        """Get billing view by account ID."""
        billing_client = self._get_billing_client()
        today = dt.datetime.now(dt.UTC).date()
        first_day_of_month = today.replace(day=1)
        next_month = today.replace(day=MINIMUM_DAYS_MONTH) + dt.timedelta(days=4)
        last_day = dt.datetime.combine(
            next_month.replace(day=1) - dt.timedelta(days=1),
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
                    "activeAfterInclusive": dt.datetime.combine(
                        first_day_of_month, dt.time.min, tzinfo=dt.UTC
                    ),
                    "activeBeforeInclusive": last_day,
                },
            },
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
        note: str,
        relationship_identifier: str,
        end_date: dt.datetime,
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
