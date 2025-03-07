import logging

import boto3
import botocore.exceptions
import requests

from swo_aws_extension.aws.errors import (
    AWSError,
    wrap_boto3_error,
    wrap_http_error,
)

logger = logging.getLogger(__name__)


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
            region_name=self.config.aws_region
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
            logger.info(f"Organization created: {response}")
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AlreadyInOrganizationException":
                logger.warning("Organization already exists")
            else:
                raise

    @wrap_boto3_error
    def activate_organizations_access(self,):
        """
        Activate the organizations access. If the access is already active,
        the function logs a warning and continues.

        :return: None
        """
        cloudformation_client = self._get_cloudformation_client()

        response = cloudformation_client.activate_organizations_access()
        logger.info(f"Organizations access activated: {response}")



