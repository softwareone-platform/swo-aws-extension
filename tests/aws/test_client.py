import datetime as dt

import pytest
from botocore.exceptions import ClientError

from swo_aws_extension.aws.client import MAX_RESULTS_PER_PAGE, get_paged_response
from swo_aws_extension.aws.errors import (
    AWSError,
    InvalidDateInTerminateResponsibilityError,
    S3BucketAlreadyOwnedError,
)


# InvalidInputException is the name given by AWS boto3 to the error we are testing:
# see more: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/organizations/client/terminate_responsibility_transfer.html#
class InvalidInputException(ClientError):  # noqa: N818
    """Dummy exception for testing purposes."""


@pytest.fixture
def mock_get_paged_response(mocker):
    return mocker.patch("swo_aws_extension.aws.client.get_paged_response", spec=True)


def test_instance_aws_client(config, aws_client_factory):
    result = aws_client_factory(config, "test_account_id", "test_role_name")

    assert result[0].credentials == {
        "AccessKeyId": "test_access_key",
        "SecretAccessKey": "test_secret_key",
        "SessionToken": "test_session_token",
    }


def test_instance_aws_client_empty_mpa_account_id(config, aws_client_factory):
    with pytest.raises(AWSError) as error:
        aws_client_factory(config, None, "test_role_name")

    assert "Parameter 'account_id' must be provided to assume the role." in str(error.value)


def test_get_inbound_transfers_success(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [{"id": "transfer1"}, {"id": "transfer2"}]

    result = mock_aws_client.get_inbound_responsibility_transfers()

    assert result == [{"id": "transfer1"}, {"id": "transfer2"}]
    mock_get_paged_response.assert_called_once_with(
        mock_client.list_inbound_responsibility_transfers,
        "ResponsibilityTransfers",
        {"Type": "BILLING", "MaxResults": MAX_RESULTS_PER_PAGE},
    )


def test_get_inbound_transfers_empty(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_inbound_responsibility_transfers()

    assert result == []
    mock_get_paged_response.assert_called_once_with(
        mock_client.list_inbound_responsibility_transfers,
        "ResponsibilityTransfers",
        {"Type": "BILLING", "MaxResults": MAX_RESULTS_PER_PAGE},
    )


def test_get_inbound_transfers_error(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.side_effect = AWSError("Some error occurred")

    with pytest.raises(AWSError, match="Some error occurred"):
        mock_aws_client.get_inbound_responsibility_transfers()

    mock_get_paged_response.assert_called_once_with(
        mock_client.list_inbound_responsibility_transfers,
        "ResponsibilityTransfers",
        {"Type": "BILLING", "MaxResults": MAX_RESULTS_PER_PAGE},
    )


def test_terminate_transfer_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
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


def test_terminate_transfer_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    transfer_id = "rt-invalid"
    end_timestamp = dt.datetime(2025, 12, 31, 23, 59, 59, tzinfo=dt.UTC)
    mock_client.exceptions.InvalidInputException = InvalidInputException
    mock_client.terminate_responsibility_transfer.side_effect = InvalidInputException(
        {
            "Error": {"Code": "InvalidInputException", "Message": "Invalid input"},
            "Reason": "SOME_REASON",
            "Message": "Some Message",
        },
        "TerminateResponsibilityTransfer",
    )

    with pytest.raises(AWSError):
        mock_aws_client.terminate_responsibility_transfer(transfer_id, end_timestamp)

    mock_client.terminate_responsibility_transfer.assert_called_once_with(
        Id=transfer_id, EndTimestamp=end_timestamp
    )


def test_terminate_transfer_invalid_date_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.exceptions.InvalidInputException = InvalidInputException
    transfer_id = "rt-transfer"
    end_timestamp = dt.datetime(2025, 12, 1, tzinfo=dt.UTC)
    mock_client.terminate_responsibility_transfer.side_effect = InvalidInputException(
        {
            "Error": {"Code": "InvalidInputException", "Message": "Invalid date"},
            "Reason": "INVALID_END_DATE",
            "Message": "Invalid date",
        },
        "TerminateResponsibilityTransfer",
    )

    with pytest.raises(InvalidDateInTerminateResponsibilityError):
        mock_aws_client.terminate_responsibility_transfer(transfer_id, end_timestamp)


def test_get_paged_response_success(mocker):
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
        method_mock, "ResponsibilityTransfers", {"Type": "BILLING", "MaxResults": 2}
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


def test_get_paged_response_custom_key(mocker):
    method_mock = mocker.Mock()
    method_mock.side_effect = [
        {
            "items": [{"id": "item1"}, {"id": "item2"}],
            "nextToken": "token1",
        },
        {
            "items": [{"id": "item3"}],
        },
    ]

    result = get_paged_response(
        method_mock, "items", {"catalog": "AWS"}, pagination_key="nextToken"
    )

    assert result == [{"id": "item1"}, {"id": "item2"}, {"id": "item3"}]
    assert method_mock.call_args_list == [
        mocker.call(catalog="AWS"),
        mocker.call(catalog="AWS", nextToken="token1"),
    ]


def test_get_paged_response_kwargs_none(mocker):
    method_mock = mocker.Mock(
        return_value={
            "ResponsibilityTransfers": [{"id": "transfer1"}],
        }
    )

    result = get_paged_response(method_mock, "ResponsibilityTransfers")

    assert result == [{"id": "transfer1"}]
    assert method_mock.call_args_list == [mocker.call()]


def test_get_paged_response_empty(mocker):
    method_mock = mocker.Mock(
        return_value={
            "ResponsibilityTransfers": [],
        }
    )

    result = get_paged_response(
        method_mock, "ResponsibilityTransfers", {"Type": "BILLING", "MaxResults": 20}
    )

    assert result == []
    assert method_mock.call_args_list == [mocker.call(MaxResults=20, Type="BILLING")]


def test_get_paged_response_single_page(mocker):
    method_mock = mocker.Mock(
        return_value={
            "ResponsibilityTransfers": [{"id": "transfer1"}, {"id": "transfer2"}],
        }
    )

    result = get_paged_response(
        method_mock, "ResponsibilityTransfers", {"Type": "BILLING", "MaxResults": 10}
    )

    assert result == [{"id": "transfer1"}, {"id": "transfer2"}]
    method_mock.assert_called_once_with(MaxResults=10, Type="BILLING")


def test_get_paged_response_empty_kwargs(mocker):
    method_mock = mocker.Mock(
        return_value={
            "ResponsibilityTransfers": [{"id": "transfer1"}],
        }
    )

    result = get_paged_response(method_mock, "ResponsibilityTransfers", {})

    assert result == [{"id": "transfer1"}]
    assert method_mock.call_args_list == [mocker.call()]


def test_invite_org_to_transfer_billing(config, aws_client_factory):
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


def test_get_transfer_details(config, aws_client_factory):
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


def test_get_cost_and_usage_success(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"Groups": [{"Keys": ["123456789"], "Metrics": {"UnblendedCost": {"Amount": "100"}}}]}
    ]

    result = mock_aws_client.get_cost_and_usage(
        start_date="2025-12-01",
        end_date="2025-12-31",
    )

    assert result == [
        {"Groups": [{"Keys": ["123456789"], "Metrics": {"UnblendedCost": {"Amount": "100"}}}]}
    ]


def test_get_cost_and_usage_with_group(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"Groups": [{"Keys": ["123456789"], "Metrics": {"UnblendedCost": {"Amount": "100"}}}]}
    ]

    result = mock_aws_client.get_cost_and_usage(
        start_date="2025-12-01",
        end_date="2025-12-31",
        group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
    )

    assert result == [
        {"Groups": [{"Keys": ["123456789"], "Metrics": {"UnblendedCost": {"Amount": "100"}}}]}
    ]


def test_get_cost_and_usage_with_filter(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_cost_and_usage(
        start_date="2025-12-01",
        end_date="2025-12-31",
        filter_by={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon EC2"]}},
    )

    assert result == []


def test_get_cost_and_usage_with_arn(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"Groups": [{"Keys": ["123456789"], "Metrics": {"UnblendedCost": {"Amount": "50"}}}]}
    ]

    result = mock_aws_client.get_cost_and_usage(
        start_date="2025-12-01",
        end_date="2025-12-31",
        view_arn="arn:aws:billing::123456789:billingview/test",
    )

    assert result == [
        {"Groups": [{"Keys": ["123456789"], "Metrics": {"UnblendedCost": {"Amount": "50"}}}]}
    ]


def test_get_cost_and_usage_empty(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_cost_and_usage(
        start_date="2025-12-01",
        end_date="2025-12-31",
    )

    assert result == []


def test_get_billing_view_success(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"arn": "arn:aws:billing::123456789:billingview/test", "name": "test-view"}
    ]

    result = mock_aws_client.get_current_billing_view_by_account_id(account_id="123456789")

    assert result == [{"arn": "arn:aws:billing::123456789:billingview/test", "name": "test-view"}]


def test_get_billing_view_empty(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_current_billing_view_by_account_id(account_id="123456789")

    assert result == []


def test_create_billing_group_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    expected_response = {"Arn": "arn:aws:billingconductor::123:billinggroup/test-billing-group"}
    mock_client.create_billing_group.return_value = expected_response

    result = mock_aws_client.create_billing_group(
        responsibility_transfer_arn="arn:aws:billing::123:responsibilitytransfer/RT-123",
        pricing_plan_arn="arn:aws:billingconductor::aws:pricingplan/BasicPricingPlan",
        name="billing-group-test",
        description="Billing group for MPA test_account_id",
    )

    assert result == expected_response
    mock_client.create_billing_group.assert_called_once_with(
        Name="billing-group-test",
        Description="Billing group for MPA test_account_id",
        ComputationPreference={
            "PricingPlanArn": "arn:aws:billingconductor::aws:pricingplan/BasicPricingPlan"
        },
        AccountGrouping={
            "ResponsibilityTransferArn": "arn:aws:billing::123:responsibilitytransfer/RT-123",
        },
    )


def test_create_billing_group_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_billing_group.side_effect = AWSError("Billing group creation failed")

    with pytest.raises(AWSError, match="Billing group creation failed"):
        mock_aws_client.create_billing_group(
            responsibility_transfer_arn="arn:aws:billing::123:responsibilitytransfer/RT-123",
            pricing_plan_arn="arn:aws:billingconductor::aws:pricingplan/BasicPricingPlan",
            name="billing-group-test",
            description="Billing group for MPA test_account_id",
        )

    mock_client.create_billing_group.assert_called_once()


def test_delete_billing_group_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    expected_response = {"Arn": "arn:aws:billingconductor::123:billinggroup/test-billing-group"}
    mock_client.delete_billing_group.return_value = expected_response

    result = mock_aws_client.delete_billing_group(
        billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-billing-group",
    )

    assert result == expected_response
    mock_client.delete_billing_group.assert_called_once_with(
        Arn="arn:aws:billingconductor::123:billinggroup/test-billing-group",
    )


def test_delete_billing_group_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.delete_billing_group.side_effect = AWSError("Billing group deletion failed")

    with pytest.raises(AWSError, match="Billing group deletion failed"):
        mock_aws_client.delete_billing_group(
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-billing-group",
        )

    mock_client.delete_billing_group.assert_called_once()


def test_get_program_management_id_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_program_management_accounts.return_value = {"items": [{"id": "pma-123456"}]}

    result = mock_aws_client.get_program_management_id_by_account(account_id="123456789")

    assert result == "pma-123456"
    mock_client.list_program_management_accounts.assert_called_once_with(
        catalog="AWS", accountIds=["123456789"]
    )


def test_get_program_management_id_empty(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_program_management_accounts.return_value = {"items": []}

    result = mock_aws_client.get_program_management_id_by_account(account_id="123456789")

    assert not result
    mock_client.list_program_management_accounts.assert_called_once_with(
        catalog="AWS", accountIds=["123456789"]
    )


def test_get_program_management_id_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_program_management_accounts.side_effect = AWSError("API error")

    with pytest.raises(AWSError, match="API error"):
        mock_aws_client.get_program_management_id_by_account(account_id="123456789")

    mock_client.list_program_management_accounts.assert_called_once()


def test_create_relationship_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    expected_response = {"relationshipIdentifier": "rel-123456"}
    mock_client.create_relationship.return_value = expected_response

    result = mock_aws_client.create_relationship_in_partner_central(
        pma_identifier="pma-123456",
        mpa_id="123456789",
        scu="SCU-001",
    )

    assert result == expected_response
    mock_client.create_relationship.assert_called_once_with(
        catalog="AWS",
        associationType="END_CUSTOMER",
        programManagementAccountIdentifier="pma-123456",
        associatedAccountId="123456789",
        displayName="SCU-001-123456789",
        resaleAccountModel="END_CUSTOMER",
        sector="COMMERCIAL",
    )


def test_create_relationship_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_relationship.side_effect = AWSError("Relationship creation failed")

    with pytest.raises(AWSError, match="Relationship creation failed"):
        mock_aws_client.create_relationship_in_partner_central(
            pma_identifier="pma-123456",
            mpa_id="123456789",
            scu="SCU-001",
        )

    mock_client.create_relationship.assert_called_once()


def test_create_channel_handshake_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    expected_response = {"handshakeIdentifier": "hs-123456"}
    mock_client.create_channel_handshake.return_value = expected_response
    end_date = dt.datetime(2026, 12, 31, tzinfo=dt.UTC)

    result = mock_aws_client.create_channel_handshake(
        pma_identifier="pma-123456",
        relationship_identifier="rel-123456",
        end_date=end_date,
        note="Please accept your Service Terms contract with SoftwareOne",
    )

    assert result == expected_response
    mock_client.create_channel_handshake.assert_called_once_with(
        handshakeType="START_SERVICE_PERIOD",
        catalog="AWS",
        associatedResourceIdentifier="rel-123456",
        payload={
            "startServicePeriodPayload": {
                "programManagementAccountIdentifier": "pma-123456",
                "servicePeriodType": "FIXED_COMMITMENT_PERIOD",
                "endDate": end_date,
                "note": "Please accept your Service Terms contract with SoftwareOne",
            }
        },
    )


def test_create_channel_handshake_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_channel_handshake.side_effect = AWSError("Handshake creation failed")
    end_date = dt.datetime(2026, 12, 31, tzinfo=dt.UTC)

    with pytest.raises(AWSError, match="Handshake creation failed"):
        mock_aws_client.create_channel_handshake(
            pma_identifier="pma-123456",
            relationship_identifier="rel-123456",
            end_date=end_date,
            note="Please accept your Service Terms contract with SoftwareOne",
        )

    mock_client.create_channel_handshake.assert_called_once()


def test_get_channel_handshakes_success(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"handshakeIdentifier": "hs-1", "status": "ACCEPTED"},
        {"handshakeIdentifier": "hs-2", "status": "PENDING"},
    ]

    result = mock_aws_client.get_channel_handshakes_by_resource(resource_identifier="rel-123456")

    assert result == [
        {"handshakeIdentifier": "hs-1", "status": "ACCEPTED"},
        {"handshakeIdentifier": "hs-2", "status": "PENDING"},
    ]
    mock_get_paged_response.assert_called_once_with(
        mock_client.list_channel_handshakes,
        "items",
        {
            "catalog": "AWS",
            "participantType": "SENDER",
            "handshakeType": "START_SERVICE_PERIOD",
            "associatedResourceIdentifiers": ["rel-123456"],
            "maxResults": MAX_RESULTS_PER_PAGE,
        },
        pagination_key="nextToken",
    )


def test_get_channel_handshakes_empty(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_channel_handshakes_by_resource(resource_identifier="rel-123456")

    assert result == []
    mock_get_paged_response.assert_called_once_with(
        mock_client.list_channel_handshakes,
        "items",
        {
            "catalog": "AWS",
            "participantType": "SENDER",
            "handshakeType": "START_SERVICE_PERIOD",
            "associatedResourceIdentifiers": ["rel-123456"],
            "maxResults": MAX_RESULTS_PER_PAGE,
        },
        pagination_key="nextToken",
    )


def test_get_channel_handshakes_error(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.side_effect = AWSError("API error")

    with pytest.raises(AWSError, match="API error"):
        mock_aws_client.get_channel_handshakes_by_resource(resource_identifier="rel-123456")

    mock_get_paged_response.assert_called_once()


def test_delete_pc_relationship_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_delete_relationship = mock_client.delete_relationship

    mock_aws_client.delete_pc_relationship(pm_identifier="pm-1", relationship_id="rel-1")  # act

    mock_delete_relationship.assert_called_once_with(
        catalog="AWS",
        identifier="rel-1",
        programManagementAccountIdentifier="pm-1",
    )


def test_delete_pc_relationship_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.delete_relationship.side_effect = AWSError("API error")

    with pytest.raises(AWSError, match="API error"):
        mock_aws_client.delete_pc_relationship(pm_identifier="pm-1", relationship_id="rel-1")

    mock_client.delete_relationship.assert_called_once_with(
        catalog="AWS",
        identifier="rel-1",
        programManagementAccountIdentifier="pm-1",
    )


def test_get_channel_handshake_by_id_found(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"id": "hs-1", "status": "ACCEPTED"},
        {"id": "hs-2", "status": "PENDING"},
        {"id": "hs-3", "status": "REJECTED"},
    ]

    result = mock_aws_client.get_channel_handshake_by_id(
        resource_identifier="rel-123456", handshake_id="hs-2"
    )

    assert result == {"id": "hs-2", "status": "PENDING"}


def test_get_channel_handshake_by_id_not_found(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {"id": "hs-1", "status": "ACCEPTED"},
        {"id": "hs-2", "status": "PENDING"},
    ]

    result = mock_aws_client.get_channel_handshake_by_id(
        resource_identifier="rel-123456", handshake_id="hs-999"
    )

    assert result is None


def test_get_channel_handshake_by_id_empty_list(
    config, aws_client_factory, mock_get_paged_response
):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_channel_handshake_by_id(
        resource_identifier="rel-123456", handshake_id="hs-1"
    )

    assert result is None


def test_list_invoice_summaries_success(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = [
        {
            "AccountId": "123456789",
            "InvoiceId": "INV-001",
            "InvoicingEntity": "AWS Inc.",
            "BillingPeriod": "2026-03",
            "InvoiceAmount": "100.00",
        }
    ]

    result = mock_aws_client.list_invoice_summaries_by_account_id("123456789", 2026, 3)

    assert len(result) == 1
    assert result[0]["InvoiceId"] == "INV-001"
    mock_get_paged_response.assert_called_once()


def test_list_s3_objects_returns_all_keys(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_paginator = mock_client.get_paginator.return_value
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {"Key": "billing/BILLING_PERIOD%3D2026-03/file1.parquet"},
                {"Key": "billing/BILLING_PERIOD%3D2026-03/file2.parquet"},
            ]
        },
        {"Contents": [{"Key": "billing/BILLING_PERIOD%3D2026-04/file3.parquet"}]},
    ]

    result = mock_aws_client.list_s3_objects("my-bucket", "billing/")

    assert result == [
        "billing/BILLING_PERIOD%3D2026-03/file1.parquet",
        "billing/BILLING_PERIOD%3D2026-03/file2.parquet",
        "billing/BILLING_PERIOD%3D2026-04/file3.parquet",
    ]
    mock_client.get_paginator.assert_called_once_with("list_objects_v2")
    mock_paginator.paginate.assert_called_once_with(Bucket="my-bucket", Prefix="billing/")


def test_list_s3_objects_empty_when_no_contents(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_paginator = mock_client.get_paginator.return_value
    mock_paginator.paginate.return_value = [{}]

    result = mock_aws_client.list_s3_objects("my-bucket", "billing/")

    assert result == []


def test_list_s3_objects_wraps_boto3_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_paginator.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "Not found"}}, "ListObjectsV2"
    )

    with pytest.raises(AWSError):
        mock_aws_client.list_s3_objects("missing-bucket", "billing/")


def test_download_s3_object_returns_bytes(config, aws_client_factory, mocker):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    expected_bytes = b"parquet-data"
    mock_body = mocker.MagicMock()
    mock_body.read.return_value = expected_bytes
    mock_client.get_object.return_value = {"Body": mock_body}

    result = mock_aws_client.download_s3_object("my-bucket", "billing/file.parquet")

    assert result == expected_bytes
    mock_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="billing/file.parquet")


def test_download_s3_object_wraps_boto3_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
    )

    with pytest.raises(AWSError):
        mock_aws_client.download_s3_object("my-bucket", "missing-key.parquet")


def test_create_s3_bucket_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not found"}},
        "HeadBucket",
    )
    mock_client.create_bucket.return_value = {}

    mock_aws_client.create_s3_bucket("swo-cur2-123456789012", "us-east-1")  # act

    mock_client.head_bucket.assert_called_once_with(Bucket="swo-cur2-123456789012")
    mock_client.create_bucket.assert_called_once_with(Bucket="swo-cur2-123456789012")


def test_create_s3_bucket_eu_region(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not found"}},
        "HeadBucket",
    )
    mock_client.create_bucket.return_value = {}

    mock_aws_client.create_s3_bucket("swo-cur2-123456789012", "eu-west-1")  # act

    mock_client.head_bucket.assert_called_once_with(Bucket="swo-cur2-123456789012")
    mock_client.create_bucket.assert_called_once_with(
        Bucket="swo-cur2-123456789012",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )


def test_create_s3_bucket_already_owned_from_head_bucket(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.head_bucket.return_value = {}

    with pytest.raises(S3BucketAlreadyOwnedError):
        mock_aws_client.create_s3_bucket("swo-cur2-123456789012", "us-east-1")

    mock_client.head_bucket.assert_called_once_with(Bucket="swo-cur2-123456789012")
    mock_client.create_bucket.assert_not_called()


def test_create_s3_bucket_already_owned_from_create_bucket_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not found"}},
        "HeadBucket",
    )
    mock_client.create_bucket.side_effect = ClientError(
        {"Error": {"Code": "BucketAlreadyOwnedByYou", "Message": "already owned"}},
        "CreateBucket",
    )

    with pytest.raises(S3BucketAlreadyOwnedError):
        mock_aws_client.create_s3_bucket("swo-cur2-123456789012", "us-east-1")

    mock_client.head_bucket.assert_called_once_with(Bucket="swo-cur2-123456789012")
    assert mock_client.create_bucket.call_count == 1


def test_create_s3_bucket_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not found"}},
        "HeadBucket",
    )
    mock_client.create_bucket.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "CreateBucket",
    )

    with pytest.raises(AWSError):
        mock_aws_client.create_s3_bucket("swo-cur2-123456789012", "us-east-1")


def test_create_s3_bucket_head_bucket_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "403", "Message": "Access denied"}},
        "HeadBucket",
    )

    with pytest.raises(AWSError):
        mock_aws_client.create_s3_bucket("swo-cur2-123456789012", "us-east-1")

    mock_client.create_bucket.assert_not_called()


def test_create_billing_export_success(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_export.return_value = {
        "ExportArn": "arn:aws:bcm-data-exports::123456789012:export/exp-001"
    }

    result = mock_aws_client.create_billing_export(
        billing_view_arn="arn:aws:billing::123456789012:billingview/billing-transfer-abc123",
        export_name="123456789012-abc123",
        s3_bucket="swo-cur2-123456789012",
        s3_prefix="cur2/123456789012/abc123",
    )

    assert result == "arn:aws:bcm-data-exports::123456789012:export/exp-001"
    mock_client.create_export.assert_called_once()
    call_kwargs = mock_client.create_export.call_args[1]
    table_configs = call_kwargs["Export"]["DataQuery"]["TableConfigurations"]
    assert (
        table_configs["COST_AND_USAGE_REPORT"]["BILLING_VIEW_ARN"]
        == "arn:aws:billing::123456789012:billingview/billing-transfer-abc123"
    )
    assert (
        call_kwargs["Export"]["DestinationConfigurations"]["S3Destination"]["S3Bucket"]
        == "swo-cur2-123456789012"
    )


def test_create_billing_export_error(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_export.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "Invalid export"}},
        "CreateExport",
    )

    with pytest.raises(AWSError):
        mock_aws_client.create_billing_export(
            billing_view_arn="arn:aws:billing::123456789012:billingview/billing-transfer-abc123",
            export_name="123456789012-abc123",
            s3_bucket="swo-cur2-123456789012",
            s3_prefix="cur2/123456789012/abc123",
        )


def test_list_existing_exports_matches_arns(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    billing_view_arn = "arn:aws:billing::123456789012:billingview/billing-transfer-abc123"
    mock_client.list_exports.return_value = {
        "Exports": [{"ExportArn": "arn:aws:bcm-data-exports::123:export/exp-001"}]
    }
    mock_client.get_export.return_value = {
        "Export": {
            "DestinationConfigurations": {
                "S3Destination": {
                    "S3Bucket": "swo-cur2-123456789012",
                    "S3Prefix": "cur2/123456789012/abc123",
                }
            },
            "DataQuery": {
                "TableConfigurations": {
                    "COST_AND_USAGE_REPORT": {"BILLING_VIEW_ARN": billing_view_arn}
                }
            },
        }
    }

    result = mock_aws_client.list_existing_billing_exports(
        s3_bucket="swo-cur2-123456789012", s3_prefix="cur2"
    )

    assert billing_view_arn in result


def test_list_existing_exports_wrong_bucket(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_exports.return_value = {
        "Exports": [{"ExportArn": "arn:aws:bcm-data-exports::123:export/exp-001"}]
    }
    mock_client.get_export.return_value = {
        "Export": {
            "DestinationConfigurations": {
                "S3Destination": {
                    "S3Bucket": "other-bucket",
                    "S3Prefix": "cur2/123456789012/abc123",
                }
            },
            "DataQuery": {
                "TableConfigurations": {"COST_AND_USAGE_REPORT": {"BILLING_VIEW_ARN": "arn:..."}}
            },
        }
    }

    result = mock_aws_client.list_existing_billing_exports(
        s3_bucket="swo-cur2-123456789012", s3_prefix="cur2"
    )

    assert result == set()


def test_list_existing_exports_empty(config, aws_client_factory):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_exports.return_value = {"Exports": []}

    result = mock_aws_client.list_existing_billing_exports(
        s3_bucket="swo-cur2-123456789012", s3_prefix="cur2"
    )

    assert result == set()
