import datetime as dt

import pytest

from swo_aws_extension.aws.client import get_paged_response
from swo_aws_extension.aws.errors import AWSError


@pytest.fixture
def mock_get_paged_response(mocker):
    return mocker.patch("swo_aws_extension.aws.client.get_paged_response", spec=True)


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


class TestGetInboundResponsibilityTransfers:
    def test_success(self, config, aws_client_factory, mock_get_paged_response):
        mock_aws_client, mock_client = aws_client_factory(
            config, "test_account_id", "test_role_name"
        )
        mock_get_paged_response.return_value = [{"id": "transfer1"}, {"id": "transfer2"}]

        result = mock_aws_client.get_inbound_responsibility_transfers()

        assert result == [{"id": "transfer1"}, {"id": "transfer2"}]
        mock_get_paged_response.assert_called_once_with(
            mock_client.list_inbound_responsibility_transfers,
            "ResponsibilityTransfers",
            {"Type": "BILLING"},
        )

    def test_empty(self, config, aws_client_factory, mock_get_paged_response):
        mock_aws_client, mock_client = aws_client_factory(
            config, "test_account_id", "test_role_name"
        )
        mock_get_paged_response.return_value = []

        result = mock_aws_client.get_inbound_responsibility_transfers()

        assert result == []
        mock_get_paged_response.assert_called_once_with(
            mock_client.list_inbound_responsibility_transfers,
            "ResponsibilityTransfers",
            {"Type": "BILLING"},
        )

    def test_error(self, config, aws_client_factory, mock_get_paged_response):
        mock_aws_client, mock_client = aws_client_factory(
            config, "test_account_id", "test_role_name"
        )
        mock_get_paged_response.side_effect = Exception("Some error occurred")

        with pytest.raises(Exception, match="Some error occurred"):
            mock_aws_client.get_inbound_responsibility_transfers()

        mock_get_paged_response.assert_called_once_with(
            mock_client.list_inbound_responsibility_transfers,
            "ResponsibilityTransfers",
            {"Type": "BILLING"},
        )


class TestTerminateResponsibilityTransfer:
    def test_success(self, config, aws_client_factory):
        mock_aws_client, mock_client = aws_client_factory(
            config, "test_account_id", "test_role_name"
        )
        end_timestamp = dt.datetime(2025, 12, 31, tzinfo=dt.UTC)
        expected_response = {
            "ResponsibilityTransfer": {
                "Arn": "string",
                "Name": "string",
                "Id": "string",
                "Type": "BILLING",
                "Status": "WITHDRAWN",
                "Source": {"ManagementAccountId": "string", "ManagementAccountEmail": "string"},
                "Target": {"ManagementAccountId": "string", "ManagementAccountEmail": "string"},
                "StartTimestamp": dt.datetime(2024, 12, 31, tzinfo=dt.UTC),
                "EndTimestamp": end_timestamp,
                "ActiveHandshakeId": "string",
            }
        }
        mock_client.terminate_responsibility_transfer.return_value = expected_response

        result = mock_aws_client.terminate_responsibility_transfer("rt-8lr3q6sn", end_timestamp)

        assert result == expected_response
        mock_client.terminate_responsibility_transfer.assert_called_once_with(
            Id="rt-8lr3q6sn", EndTimestamp=end_timestamp
        )

    def test_error(self, config, aws_client_factory):
        mock_aws_client, mock_client = aws_client_factory(
            config, "test_account_id", "test_role_name"
        )
        transfer_id = "rt-invalid"
        end_timestamp = dt.datetime(2025, 12, 31, 23, 59, 59, tzinfo=dt.UTC)
        mock_client.terminate_responsibility_transfer.side_effect = Exception("Transfer not found")

        with pytest.raises(Exception, match="Transfer not found"):
            mock_aws_client.terminate_responsibility_transfer(transfer_id, end_timestamp)

        mock_client.terminate_responsibility_transfer.assert_called_once_with(
            Id=transfer_id, EndTimestamp=end_timestamp
        )


class TestGetPagedResponse:
    def test_success(self, mocker):
        """Test get_paged_response with multiple pages."""
        method_mock = mocker.Mock()
        method_mock.side_effect = [
            {
                "ResponsibilityTransfers": [{"id": "transfer1"}, {"id": "transfer2"}],
                "NextToken": "token1",
            },
            {
                "ResponsibilityTransfers": [{"id": "transfer3"}],
            },
        ]

        result = get_paged_response(
            method_mock, "ResponsibilityTransfers", {"Type": "BILLING"}, max_results=2
        )

        assert result == [
            {"id": "transfer1"},
            {"id": "transfer2"},
            {"id": "transfer3"},
        ]
        assert method_mock.call_args_list == [
            mocker.call(MaxResults=2, Type="BILLING"),
            mocker.call(MaxResults=2, NextToken="token1", Type="BILLING"),
        ]

    def test_with_kwargs_none(self, mocker):
        """Test get_paged_response with kwargs=None (default value)."""
        method_mock = mocker.Mock(
            return_value={
                "ResponsibilityTransfers": [{"id": "transfer1"}],
            }
        )

        result = get_paged_response(method_mock, "ResponsibilityTransfers")

        assert result == [{"id": "transfer1"}]
        assert method_mock.call_args_list == [mocker.call(MaxResults=20)]

    def test_empty_initial_response(self, mocker):
        """Test get_paged_response with an empty initial response."""
        method_mock = mocker.Mock(
            return_value={
                "ResponsibilityTransfers": [],
            }
        )

        result = get_paged_response(method_mock, "ResponsibilityTransfers", {"Type": "BILLING"})

        assert result == []
        assert method_mock.call_args_list == [mocker.call(MaxResults=20, Type="BILLING")]

    def test_single_page_no_next_token(self, mocker):
        """Test get_paged_response with a single page (no NextToken in response)."""
        method_mock = mocker.Mock(
            return_value={
                "ResponsibilityTransfers": [{"id": "transfer1"}, {"id": "transfer2"}],
            }
        )

        result = get_paged_response(
            method_mock, "ResponsibilityTransfers", {"Type": "BILLING"}, max_results=10
        )

        assert result == [{"id": "transfer1"}, {"id": "transfer2"}]
        # Should only be called once since there's no NextToken
        method_mock.assert_called_once_with(MaxResults=10, Type="BILLING")

    def test_with_empty_kwargs(self, mocker):
        """Test get_paged_response with explicitly empty kwargs dict."""
        method_mock = mocker.Mock(
            return_value={
                "ResponsibilityTransfers": [{"id": "transfer1"}],
            }
        )

        result = get_paged_response(method_mock, "ResponsibilityTransfers", {})

        assert result == [{"id": "transfer1"}]
        assert method_mock.call_args_list == [mocker.call(MaxResults=20)]


def test_invite_organization_to_transfer_billing(
    config, aws_client_factory, mock_get_paged_response
):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.invite_organization_to_transfer_responsibility.return_value = {
        "Handshake": {
            "Resources": [
                {"Type": "RESPONSIBILITY_TRANSFER", "Value": "RT-123"},
            ]
        }
    }

    result = mock_aws_client.invite_organization_to_transfer_billing(
        customer_id="test_account_id", start_timestamp=1767225600, source_name="test_source_name"
    )

    assert result == {
        "Handshake": {
            "Resources": [
                {"Type": "RESPONSIBILITY_TRANSFER", "Value": "RT-123"},
            ]
        }
    }
    mock_client.invite_organization_to_transfer_responsibility.assert_called_once_with(
        Type="BILLING",
        Target={"Id": "test_account_id", "Type": "ACCOUNT"},
        StartTimestamp=1767225600,
        SourceName="test_source_name",
    )


def test_get_responsibility_transfer_details(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.describe_responsibility_transfer.return_value = {
        "ResponsibilityTransfer": {
            "Id": "RT-123",
            "Status": "PENDING",
        }
    }

    result = mock_aws_client.get_responsibility_transfer_details(transfer_id="RT-123")

    assert result == {
        "ResponsibilityTransfer": {
            "Id": "RT-123",
            "Status": "PENDING",
        }
    }
    mock_client.describe_responsibility_transfer.assert_called_once_with(Id="RT-123")
