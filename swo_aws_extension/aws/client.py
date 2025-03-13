import logging
from dataclasses import dataclass
from typing import Optional

import boto3
import botocore.exceptions
import requests

from swo_aws_extension.aws.errors import (
    AWSError,
    wrap_boto3_error,
    wrap_http_error,
)

logger = logging.getLogger(__name__)


@dataclass
class AccountCreationStatus:
    account_request_id: str
    status: str
    account_name: str
    failure_reason: Optional[str] = None
    account_id: Optional[str] = None

    @classmethod
    def from_boto3_response(cls, response):
        """
        Create an AccountCreationStatus object from a boto3 response.
        Args:
            response: The boto3 response.

        Returns:
            AccountCreationStatus: The AccountCreationStatus object.

        """
        status_info = response["CreateAccountStatus"]
        return cls(
            account_request_id=status_info["Id"],
            status=status_info["State"],
            account_name=status_info["AccountName"],
            failure_reason=status_info.get("FailureReason"),
            account_id=status_info.get("AccountId"),
        )

    def __str__(self):
        failure_info = (
            f", Failure Reason: {self.failure_reason}" if self.failure_reason else ""
        )
        account_info = f", Account ID: {self.account_id}" if self.account_id else ""
        return (
            f"AccountCreationStatus(Name: {self.account_name}, "
            f"ID: {self.account_request_id}, "
            f"Status: {self.status}{failure_info}{account_info})"
        )


class AWSClient:
    def __init__(self, config, mpa_account_id, role_name) -> None:
        self.config = config
        self.mpa_account_id = mpa_account_id
        self.role_name = role_name
        self.access_token = self._get_access_token()
        self.credentials = self._get_credentials()

    @wrap_http_error
    def _get_access_token(self):
        """
        Get the OpenID Connect access token.

        :return: str The OpenID Connect access token.
        """
        url = self.config.ccp_oauth_url
        payload = {
            "client_id": self.config.ccp_client_id,
            "client_secret": self.config.ccp_client_secret,
            "grant_type": "client_credentials",
            "scope": self.config.aws_openid_scope,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        logger.info("OpenId Access token issued")
        response_data = response.json()
        return response_data["access_token"]

    @wrap_boto3_error
    def _get_credentials(self):
        """
        Get the credentials for the assumed role.

        :return: dict() The credentials for the assumed role.
        """
        if not self.mpa_account_id:
            raise AWSError(
                "Parameter 'mpa_account_id' must be provided to assume the role."
            )

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
        :return: The organization client.
        """
        return boto3.client(
            "organizations",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
        )

    def _get_cloudformation_client(self):
        """
        Get the cloudformation client.
        :return: The cloudformation client.
        """
        return boto3.client(
            "cloudformation",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name=self.config.aws_region,
        )

    @wrap_boto3_error
    def create_organization(self):
        """
        Create an organization. If the organization already exists,
        the function logs a warning and continues.

        :return: None
        """
        org_client = self._get_organization_client()
        try:
            response = org_client.create_organization(FeatureSet="ALL")
            logger.info(
                f"Organization created with Id {response['Organization']['Id']}"
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AlreadyInOrganizationException":
                logger.warning("Organization already exists. Skipping creation.")
            else:
                raise

    @wrap_boto3_error
    def activate_organizations_access(
        self,
    ):
        """
        Activate the organizations access. If the access is already active,
        the function logs a warning and continues.

        :return: None
        """
        cloudformation_client = self._get_cloudformation_client()

        cloudformation_client.activate_organizations_access()
        logger.info("Organizations access activated")

    @wrap_boto3_error
    def create_linked_account(
        self, email, account_name, role_name="OrganizationAccountAccessRole"
    ):
        """
        Create a linked account.

        :param email: The email of the account.
        :param account_name: The name of the account.
        :param role_name: The role name. By defaults: OrganizationAccountAccessRole
        :return: AccountCreationStatus The status of the linked account creation.
        """
        org_client = self._get_organization_client()
        response = org_client.create_account(
            Email=email,
            AccountName=account_name,
            RoleName=role_name,
            IamUserAccessToBilling="DENY",
        )
        account_creation_status = AccountCreationStatus.from_boto3_response(response)
        logger.info(f"Linked account created: {account_creation_status}")
        return account_creation_status

    @wrap_boto3_error
    def get_linked_account_status(self, create_account_request_id):
        """
        Get the status of a linked account.

        :param create_account_request_id: The request ID from create_account call.
        :return: AccountCreationStatus The status of the linked account.
        """
        org_client = self._get_organization_client()
        response = org_client.describe_create_account_status(
            CreateAccountRequestId=create_account_request_id
        )
        account_creation_status = AccountCreationStatus.from_boto3_response(response)
        logger.info(f"Linked account request status: {account_creation_status}")
        return account_creation_status

    @wrap_boto3_error
    def list_accounts(self):
        """
        List the accounts in the organization.

        :return: list({
            'Id': 'string',
            'Arn': 'string',
            'Email': 'string',
            'Name': 'string',
            'Status': 'ACTIVE'|'SUSPENDED'|'PENDING_CLOSURE',
            'JoinedMethod': 'INVITED'|'CREATED',
            'JoinedTimestamp': datetime(2015, 1, 1)
        }) The accounts in the organization.
        """
        org_client = self._get_organization_client()
        accounts = []
        response = org_client.list_accounts()
        accounts.extend(response.get("Accounts", []))
        while response.get("NextToken"):
            response = org_client.list_accounts(NextToken=response["NextToken"])
            accounts.extend(response.get("Accounts", []))
        return accounts

    @wrap_boto3_error
    def close_account(self, account_id):
        """
        Close the account.

        :return: None
        """
        try:
            org_client = self._get_organization_client()
            return org_client.close_account(AccountId=account_id)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AccountAlreadyClosedException":
                logger.warning(f"Account {account_id} already closed")
            else:
                raise
