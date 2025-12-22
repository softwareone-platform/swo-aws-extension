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

logger = logging.getLogger(__name__)


def get_paged_response(
    method_to_call: Callable, data_key: str, kwargs: dict | None = None, max_results: int = 20
) -> list:
    """Retrieves paginated data from API."""
    response_data, next_token = _get_response(method_to_call, kwargs, data_key, max_results)
    while next_token:
        r_data, next_token = _get_response(
            method_to_call, kwargs, data_key, max_results, next_token
        )
        response_data.extend(r_data)

    return response_data


def _get_response(
    method_to_call: Callable, kwargs: dict, data_key: str, max_results: int, next_token=""
) -> tuple[list, str | None]:
    call_args = dict(kwargs or {})
    if next_token:
        call_args["NextToken"] = next_token
    response = method_to_call(MaxResults=max_results, **call_args)

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
            {"Type": "BILLING"},
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
