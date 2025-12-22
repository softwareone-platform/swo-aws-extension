import datetime as dt
import logging
from collections.abc import Callable

import boto3
import requests

from swo_aws_extension.aws.errors import (
    AWSError,
    wrap_boto3_error,
    wrap_http_error,
)
from swo_aws_extension.swo.ccp.client import CCPClient

MINIMUM_DAYS_MONTH = 28
MAX_RESULTS_PER_PAGE = 20

logger = logging.getLogger(__name__)


def get_paged_response(method_to_call: Callable, data_key: str, kwargs: dict | None = None) -> list:
    """Retrieves paginated data from API."""
    response_data, next_token = _get_response(method_to_call, kwargs, data_key)
    while next_token:
        r_data, next_token = _get_response(method_to_call, kwargs, data_key, next_token)
        response_data.extend(r_data)

    return response_data


def _get_response(
    method_to_call: Callable, kwargs: dict, data_key: str, next_token=""
) -> tuple[list, str | None]:
    call_args = dict(kwargs or {})
    if next_token:
        call_args["NextToken"] = next_token
    response = method_to_call(**call_args)

    return response.get(data_key, []), response.get("NextToken")


class AWSClient:
    """AWS client."""

    def __init__(self, config, pma_account_id, role_name) -> None:
        self.config = config
        self.pma_account_id = pma_account_id
        self.role_name = role_name
        self.access_token = self._get_access_token()
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

    @wrap_http_error
    def _get_access_token(self):
        ccp_client = CCPClient(self.config)
        payload = {
            "client_id": self.config.ccp_client_id,
            "client_secret": ccp_client.get_secret_from_key_vault(),
            "grant_type": "client_credentials",
            "scope": self.config.aws_openid_scope,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(
            self.config.ccp_oauth_url, headers=headers, data=payload, timeout=60
        )
        response.raise_for_status()
        logger.info("OpenId Access token issued")
        response_data = response.json()
        return response_data["access_token"]

    @wrap_boto3_error
    def _get_credentials(self):
        if not self.pma_account_id:
            raise AWSError("Parameter 'mpa_account_id' must be provided to assume the role.")

        role_arn = f"arn:aws:iam::{self.pma_account_id}:role/{self.role_name}"
        response = boto3.client("sts").assume_role_with_web_identity(
            RoleArn=role_arn,
            RoleSessionName="SWOExtensionOnboardingSession",
            WebIdentityToken=self.access_token,
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
