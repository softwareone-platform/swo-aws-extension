import logging
from dataclasses import dataclass

import boto3
import botocore.exceptions
import requests
from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.aws.errors import (
    AWSError,
    wrap_boto3_error,
    wrap_http_error,
)
from swo_ccp_client.client import CCPClient

logger = logging.getLogger(__name__)


@dataclass
class AccountCreationStatus:
    """AWS account creation status."""

    account_request_id: str
    status: str
    account_name: str
    failure_reason: str | None = None
    account_id: str | None = None

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
        failure_info = f", Failure Reason: {self.failure_reason}" if self.failure_reason else ""
        account_info = f", Account ID: {self.account_id}" if self.account_id else ""
        return (
            f"AccountCreationStatus(Name: {self.account_name}, "
            f"ID: {self.account_request_id}, "
            f"Status: {self.status}{failure_info}{account_info})"
        )


class AWSClient:
    """AWS client."""

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

        Returns:
            The OpenID Connect access token.
        """
        ccp_client = CCPClient(self.config)
        url = self.config.ccp_oauth_url
        payload = {
            "client_id": self.config.ccp_client_id,
            "client_secret": ccp_client.get_secret_from_key_vault(),
            "grant_type": "client_credentials",
            "scope": self.config.aws_openid_scope,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, headers=headers, data=payload, timeout=60)
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

    def _get_cloudformation_client(self):
        """
        Get the cloudformation client.

        Returns:
            The cloudformation client.
        """
        return boto3.client(
            "cloudformation",
            aws_access_key_id=self.credentials["AccessKeyId"],
            aws_secret_access_key=self.credentials["SecretAccessKey"],
            aws_session_token=self.credentials["SessionToken"],
            region_name=self.config.aws_region,
        )

    def _get_sts_client(self):
        """
        Get the STS client.

        Returns:
            The STS client.
        """
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

    @wrap_boto3_error
    def get_caller_identity(self):
        """Method used to validate credentials."""
        sts_client = self._get_sts_client()
        sts_client.get_caller_identity()

    @wrap_boto3_error
    def create_organization(self):
        """
        Create an organization. If the organization already exists.

        The function logs a warning and continues.
        """
        org_client = self._get_organization_client()
        try:
            response = org_client.create_organization(FeatureSet="ALL")
            logger.info("Organization created with Id %s", response["Organization"]["Id"])
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
        Activate the organizations access.

        If the access is already active, the function logs a warning and continues.
        """
        cloudformation_client = self._get_cloudformation_client()

        cloudformation_client.activate_organizations_access()
        logger.info("Organizations access activated")

    @wrap_boto3_error
    def create_linked_account(self, email, account_name, role_name="OrganizationAccountAccessRole"):
        """
        Create a linked account.

        Args:
            email: The email of the account.
            account_name: The name of the account.
            role_name: The role name. By defaults: OrganizationAccountAccessRole

        Returns:
            AccountCreationStatus The status of the linked account creation.
        """
        org_client = self._get_organization_client()
        response = org_client.create_account(
            Email=email, AccountName=account_name, RoleName=role_name, IamUserAccessToBilling="DENY"
        )
        return AccountCreationStatus.from_boto3_response(response)

    @wrap_boto3_error
    def get_linked_account_status(self, create_account_request_id):
        """
        Get the status of a linked account.

        Args:
            create_account_request_id: The request ID from create_account call.

        Returns:
            AccountCreationStatus The status of the linked account.
        """
        org_client = self._get_organization_client()
        response = org_client.describe_create_account_status(
            CreateAccountRequestId=create_account_request_id
        )
        return AccountCreationStatus.from_boto3_response(response)

    @wrap_boto3_error
    def list_accounts(self):
        """
        List the accounts in the organization.

        Returns:
            AWS account list in the organization.
            list({
                'Id': 'string',
                'Arn': 'string',
                'Email': 'string',
                'Name': 'string',
                'Status': 'ACTIVE'|'SUSPENDED'|'PENDING_CLOSURE',
                'JoinedMethod': 'INVITED'|'CREATED',
                'JoinedTimestamp': datetime(2015, 1, 1)
            })
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
    def describe_organization(self):
        """
        Describe organization.

        Returns:
            AWS organization
            {
                "MasterAccountArn":
                "arn:aws:organizations::111111111111:account/o-exampleorgid/111111111111",
                "MasterAccountEmail": "bill@example.com",
                "MasterAccountId": "111111111111",
                "Id": "o-exampleorgid",
                "FeatureSet": "ALL",
                "Arn": "arn:aws:organizations::111111111111:organization/o-exampleorgid",
                "AvailablePolicyTypes": [
                        {
                                "Status": "ENABLED",
                                "Type": "SERVICE_CONTROL_POLICY"
                        }
                ]
            }
        """
        org_client = self._get_organization_client()
        response = org_client.describe_organization()
        return response.get("Organization", None)

    def invite_account_to_organization(self, account_id, notes=None):
        """
        Invite an AWS account to join the organization.

        Args:
            account_id (str): The AWS account ID to invite.
            notes (str): organization notes.

        Returns (Handshake):
            dict: A dictionary containing details of the handshake, including:
                - Id (str): The handshake ID.
                - Arn (str): The Amazon Resource Name (ARN) of the handshake.
                - Parties (list[dict]): A list of parties involved in the handshake, each with:
                    - Id (str): The identifier of the party.
                    - Type (str): The type of the party ('ACCOUNT', 'ORGANIZATION', or 'EMAIL').
                - State (str): The current state of the handshake
                   ('REQUESTED', 'OPEN', 'CANCELED', 'ACCEPTED', 'DECLINED', 'EXPIRED').
                - RequestedTimestamp (datetime): The time the handshake was requested.
                - ExpirationTimestamp (datetime): The time the handshake expires.
                - Action (str): The action associated with the handshake
                    ('INVITE', 'ENABLE_ALL_FEATURES', etc.).
                - Resources (list[dict]): A list of resources associated with the handshake.

        Raises:
            Organizations.Client.exceptions.AccessDeniedException: If access is denied.
            Organizations.Client.exceptions.AWSOrganizationsNotInUseException:
                If AWS Organizations is not in use.
            Organizations.Client.exceptions.AccountOwnerNotVerifiedException:
                If the account owner is not verified.
            Organizations.Client.exceptions.ConcurrentModificationException:
                If a concurrent modification occurs.
            Organizations.Client.exceptions.HandshakeConstraintViolationException:
                If handshake constraints are violated.
            Organizations.Client.exceptions.DuplicateHandshakeException:
                If a duplicate handshake is detected.
            Organizations.Client.exceptions.ConstraintViolationException:
                If a constraint is violated.
            Organizations.Client.exceptions.InvalidInputException: If the input is invalid.
            Organizations.Client.exceptions.FinalizingOrganizationException:
                If the organization is being finalized.
            Organizations.Client.exceptions.ServiceException: If a service error occurs.
            Organizations.Client.exceptions.TooManyRequestsException: If too many requests are made.

        see: https://boto3.amazonaws.com/v1/documentation/api/1.26.92/reference/services/organizations/client/invite_account_to_organization.html
        """
        org_client = self._get_organization_client()
        try:
            response = org_client.invite_account_to_organization(
                Target={"Id": account_id, "Type": "ACCOUNT"},
                Notes=notes,
            )
            return response.get("Handshake", None)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "DuplicateHandshakeException":
                logger.exception(
                    "Failed to invite account %s to the organization: %s",
                    account_id,
                    e.response["Error"]["Message"],
                )
            else:
                raise

    def list_handshakes_for_organization(self):
        """
        List all handshakes in the organization.

        Returns:
            List of handshakes
        """
        org_client = self._get_organization_client()
        filter_handshake = {"ActionType": "INVITE"}
        response = org_client.list_handshakes_for_organization(Filter=filter_handshake)
        handshakes = response.get("Handshakes", [])
        while response.get("NextToken"):
            response = org_client.list_handshakes_for_organization(
                NextToken=response["NextToken"], Filter=filter_handshake
            )
            handshakes.extend(response.get("Handshakes", []))
        return handshakes

    def cancel_handshake(self, handshake_id):
        """
        Cancel a handshake.

        Args:
            handshake_id: The ID of the handshake to cancel.
        """
        org_client = self._get_organization_client()
        return org_client.cancel_handshake(HandshakeId=handshake_id)

    @wrap_boto3_error
    def enable_scp(self):
        """Enable SCP for the organization."""
        org_client = self._get_organization_client()

        root = org_client.list_roots()["Roots"][0]

        policy = find_first(
            lambda p: p.get("Type") == "SERVICE_CONTROL_POLICY", root.get("PolicyTypes", []), None
        )
        if policy and policy.get("Status", "") == "ENABLED":
            logger.info("Policy Already Enabled for root %s. Skipping.", root["Id"])
            return

        org_client.enable_policy_type(RootId=root["Id"], PolicyType="SERVICE_CONTROL_POLICY")
        logger.info("SCP has been enabled")

    def account_aliases(self):
        """Returns AWS account aliases."""
        iam_client = self._get_client("iam")
        response = iam_client.list_account_aliases()
        return response.get("AccountAliases", [])

    def account_name(self) -> str:
        """Account name."""
        return self.account_aliases()[0] if self.account_aliases() else ""

    @wrap_boto3_error
    def list_invoice_summaries_by_account_id(self, account_id, year, month):
        """
        List invoice summaries for the specified date range.

        Args:
            account_id (str): The AWS account ID for which to list invoice summaries.
            year (int): The year of the billing period.
            month (int): The month of the billing period (1-12).

        Returns:
            list[dict]: A list of invoice summaries for the specified account and billing period.
        """
        invoicing_client = self._get_invoicing_client()

        invoice_summaries = []
        selector = {"ResourceType": "ACCOUNT_ID", "Value": account_id}
        billing_period_filter = {"BillingPeriod": {"Month": month, "Year": year}}

        response = invoicing_client.list_invoice_summaries(
            Selector=selector,
            Filter=billing_period_filter,
        )
        invoice_summaries.extend(response.get("InvoiceSummaries", []))

        while response.get("NextToken"):
            response = invoicing_client.list_invoice_summaries(
                Selector=selector, Filter=billing_period_filter, NextToken=response["NextToken"]
            )
            invoice_summaries.extend(response.get("InvoiceSummaries", []))
        return invoice_summaries

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
