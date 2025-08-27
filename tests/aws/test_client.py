from unittest.mock import call

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
    assert "Parameter 'mpa_account_id' must be provided to assume the role." in str(e.value)


def test_create_organization_success(config, aws_client_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_organization.return_value = {"Organization": {"Id": "test_organization"}}

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

    with pytest.raises(AWSError) as e:
        aws_client.create_organization()
    assert "AccessDeniedForDependencyException" in str(e.value)


def test_aws_client_list_accounts(mocker, config, aws_client_factory, data_aws_account_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_accounts.side_effect = [
        {
            "Accounts": [data_aws_account_factory(aws_id=f"0000-{0:04}-{j:04}") for j in range(10)],
            "NextToken": "token0",
        },
        {
            "Accounts": [data_aws_account_factory(aws_id=f"0000-{1:04}-{j:04}") for j in range(10)],
        },
    ]

    accounts = aws_client.list_accounts()
    assert len(accounts) == 20
    expected_calls = [call(), call(NextToken="token0")]
    mock_client.list_accounts.assert_has_calls(expected_calls)


def test_enable_scp(config, aws_client_factory, roots_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_roots.return_value = roots_factory()
    mock_client.enable_policy_type.return_value = roots_factory()

    aws_client.enable_scp()
    mock_client.list_roots.assert_called_once_with()
    mock_client.enable_policy_type.assert_called_once_with(
        RootId="root_id", PolicyType="SERVICE_CONTROL_POLICY"
    )


def test_enable_scp_already_enabled(config, aws_client_factory, roots_factory):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_roots.return_value = roots_factory(
        policy_types=[{"Type": "SERVICE_CONTROL_POLICY", "Status": "ENABLED"}]
    )

    aws_client.enable_scp()
    mock_client.list_roots.assert_called_once_with()
    mock_client.enable_policy_type.assert_not_called()


def test_aws_client_list_invoice_summaries(
    mocker, config, aws_client_factory, data_aws_invoice_summary_factory
):
    account_id = "test_account_id"
    aws_client, mock_client = aws_client_factory(config, account_id, "test_role_name")
    mock_client.list_invoice_summaries.side_effect = [
        {
            "InvoiceSummaries": [data_aws_invoice_summary_factory()],
            "NextToken": "token0",
        },
        {
            "InvoiceSummaries": [data_aws_invoice_summary_factory()],
        },
    ]
    year = 2025
    month = 2

    list_invoices = aws_client.list_invoice_summaries_by_account_id(account_id, year, month)
    assert len(list_invoices) == 2
    expected_calls = [
        call(
            Selector={"ResourceType": "ACCOUNT_ID", "Value": account_id},
            Filter={"BillingPeriod": {"Month": month, "Year": year}},
        ),
        call(
            Selector={"ResourceType": "ACCOUNT_ID", "Value": account_id},
            Filter={"BillingPeriod": {"Month": month, "Year": year}},
            NextToken="token0",
        ),
    ]
    mock_client.list_invoice_summaries.assert_has_calls(expected_calls)


def test_aws_client_get_cost_and_usage(
    mocker, config, aws_client_factory, data_aws_cost_and_usage_factory
):
    account_id = "test_account_id"
    aws_client, mock_client = aws_client_factory(config, account_id, "test_role_name")
    aws_cost_and_usage = data_aws_cost_and_usage_factory()
    aws_cost_and_usage["NextPageToken"] = "token0"
    mock_client.get_cost_and_usage.side_effect = [
        aws_cost_and_usage,
        data_aws_cost_and_usage_factory(),
    ]

    start_date = "2025-01-01"
    end_date = "2025-02-01"
    group_by = [{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}]
    filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}

    cost_and_usage = aws_client.get_cost_and_usage(start_date, end_date, group_by, filter_by)
    assert len(cost_and_usage[0]["Groups"]) == 2
    expected_calls = [
        call(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=group_by,
            Filter=filter_by,
        ),
        call(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=group_by,
            Filter=filter_by,
            NextPageToken="token0",
        ),
    ]
    mock_client.get_cost_and_usage.assert_has_calls(expected_calls)
