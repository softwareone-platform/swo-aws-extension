from unittest.mock import call

import pytest

from swo_aws_extension.aws.errors import AWSError


def test_instance_aws_client(config, aws_client_factory):
    result = aws_client_factory(config, "test_account_id", "test_role_name")

    assert result[0].access_token == "test_access_token"
    assert result[0].credentials == {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }


def test_instance_aws_client_empty_mpa_account_id(config, aws_client_factory):
    with pytest.raises(AWSError) as error:
        aws_client_factory(config, None, "test_role_name")

    assert "Parameter 'mpa_account_id' must be provided to assume the role." in str(error.value)


def test_aws_client_get_cost_and_usage(
    mocker, config, aws_client_factory, data_aws_cost_and_usage_factory
):
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    aws_cost_and_usage = data_aws_cost_and_usage_factory()
    aws_cost_and_usage["NextPageToken"] = "token0"
    mock_client.get_cost_and_usage.side_effect = [
        aws_cost_and_usage,
        data_aws_cost_and_usage_factory(),
    ]

    result = aws_client.get_cost_and_usage(
        "2025-01-01",
        "2025-02-01",
        [{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": ["test_account_id"]}},
    )

    assert len(result[0]["Groups"]) == 2
    expected_calls = [
        call(
            TimePeriod={"Start": "2025-01-01", "End": "2025-02-01"},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
            Filter={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": ["test_account_id"]}},
        ),
        call(
            TimePeriod={"Start": "2025-01-01", "End": "2025-02-01"},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
            Filter={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": ["test_account_id"]}},
            NextPageToken="token0",
        ),
    ]
    mock_client.get_cost_and_usage.assert_has_calls(expected_calls)
