import botocore.exceptions
import pytest

from swo_aws_extension.aws.errors import AWSError


def test_instance_aws_client(config, aws_client_factory):
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    assert aws_client.access_token == "test_access_token"
    assert aws_client.credentials == {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }


def test_instance_aws_client_empty_mpa_account_id(config, aws_client_factory):
    with pytest.raises(AWSError) as e:
        aws_client_factory(config, None, "test_role_name")
    assert ("Parameter 'mpa_account_id' must be provided to assume the role." in str(e.value))


def test_create_organization_success(config, aws_client_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_organization.return_value = {
        "Organization": "test_organization"
    }

    aws_client.create_organization()
    mock_client.create_organization.assert_called_once_with(FeatureSet="ALL")


def test_create_organization_already_exists(config, aws_client_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    error_response = {
        "Error": {
            "Code": "AlreadyInOrganizationException",
            "Message": "The account is already part of an organization.",
        }
    }
    mock_client.create_organization.side_effect = botocore.exceptions.ClientError(
        error_response, "CreateOrganization"
    )

    aws_client.create_organization()
    assert mock_client.create_organization.call_count == 1


def test_create_organization_error(config, aws_client_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    error_response = {
        "Error": {
            "Code": "AccessDeniedForDependencyException",
            "Message": "The request failed because your credentials do not have permission"
                       " to create the service-linked role required by AWS Organizations",
        }
    }
    mock_client.create_organization.side_effect = botocore.exceptions.ClientError(
        error_response, "CreateOrganization"
    )

    with pytest.raises(botocore.exceptions.ClientError) as e:
        aws_client.create_organization()
    assert "AccessDeniedForDependencyException" in str(e.value)
