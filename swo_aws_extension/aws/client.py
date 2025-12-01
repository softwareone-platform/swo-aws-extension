import logging

import boto3
import requests

from swo_aws_extension.aws.errors import (
    AWSError,
    wrap_boto3_error,
    wrap_http_error,
)
from swo_aws_extension.swo_ccp.client import CCPClient

logger = logging.getLogger(__name__)


class AWSClient:
    """AWS client."""

    def __init__(self, config, mpa_account_id, role_name) -> None:
        self.config = config
        self.mpa_account_id = mpa_account_id
        self.role_name = role_name
        self.access_token = self._get_access_token()
        self.credentials = self._get_credentials()

    @wrap_boto3_error
    def get_cost_and_usage(
        self,
        start_date,
        end_date,
        group_by=None,
        filter_by=None,
    ):
        """
        Get cost and usage data for the specified date range.

        Args:
            start_date (str): The start date in 'YYYY-MM-DD' format.
            end_date (str): The end date in 'YYYY-MM-DD' format.
            group_by (list[dict], optional): List of dictionaries specifying how to group the data.
            filter_by (dict, optional): Dictionary specifying the filter criteria for the data.

        Returns:
            list[dict]: A list of dictionaries containing cost and usage data for the specified
            date range.
        """
        ce_client = self._get_cost_explorer_client()
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=group_by or [],
            Filter=filter_by or {},
        )
        reports = response.get("ResultsByTime", [])
        while response.get("NextPageToken"):
            response = ce_client.get_cost_and_usage(
                TimePeriod={"Start": start_date, "End": end_date},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=group_by or [],
                Filter=filter_by or {},
                NextPageToken=response["NextPageToken"],
            )
            reports.extend(response.get("ResultsByTime", []))
        return reports

    @wrap_http_error
    def _get_access_token(self):
        """
        Get the OpenID Connect access token.

        Returns:
            The OpenID Connect access token.
        """
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
        """
        Get the credentials for the assumed role.

        Returns:
            The credentials for the assumed role.
        """
        if not self.mpa_account_id:
            raise AWSError("Parameter 'mpa_account_id' must be provided to assume the role.")

        role_arn = f"arn:aws:iam::{self.mpa_account_id}:role/{self.role_name}"
        response = boto3.client("sts").assume_role_with_web_identity(
            RoleArn=role_arn,
            RoleSessionName="SWOExtensionOnboardingSession",
            WebIdentityToken=self.access_token,
        )
        return response["Credentials"]

    def _get_organization_client(self):
        """
        Get the organization client.

        Returns:
            The organization client.
        """
        return self._get_client("organizations")

    def _get_client(self, service_name):
        """
        Get the organization client.

        Returns:
            The organization client.
        """
        return boto3.client(
            service_name,
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
        )

    def _get_invoicing_client(self):
        """
        Get the Invoicing client.

        Returns:
            The Invoicing client.
        """
        return boto3.client(
            "invoicing",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name=self.config.aws_region,
        )
