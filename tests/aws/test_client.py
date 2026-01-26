import datetime as dt

import pytest

from swo_aws_extension.aws.client import get_paged_response
from swo_aws_extension.aws.errors import AWSError


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
        {"Type": "BILLING", "MaxResults": 20},
    )


def test_get_inbound_transfers_empty(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.return_value = []

    result = mock_aws_client.get_inbound_responsibility_transfers()

    assert result == []
    mock_get_paged_response.assert_called_once_with(
        mock_client.list_inbound_responsibility_transfers,
        "ResponsibilityTransfers",
        {"Type": "BILLING", "MaxResults": 20},
    )


def test_get_inbound_transfers_error(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.side_effect = AWSError("Some error occurred")

    with pytest.raises(AWSError, match="Some error occurred"):
        mock_aws_client.get_inbound_responsibility_transfers()

    mock_get_paged_response.assert_called_once_with(
        mock_client.list_inbound_responsibility_transfers,
        "ResponsibilityTransfers",
        {"Type": "BILLING", "MaxResults": 20},
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
    mock_client.terminate_responsibility_transfer.side_effect = AWSError("Transfer not found")

    with pytest.raises(AWSError, match="Transfer not found"):
        mock_aws_client.terminate_responsibility_transfer(transfer_id, end_timestamp)

    mock_client.terminate_responsibility_transfer.assert_called_once_with(
        Id=transfer_id, EndTimestamp=end_timestamp
    )


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
        note="Test handshake",
        relationship_identifier="rel-123456",
        end_date=end_date,
    )

    assert result == expected_response
    mock_client.create_channel_handshake.assert_called_once_with(
        handshakeType="START_SERVICE_PERIOD",
        catalog="AWS",
        associatedResourceIdentifier="rel-123456",
        payload={
            "startServicePeriodPayload": {
                "programManagementAccountIdentifier": "pma-123456",
                "note": "Test handshake",
                "servicePeriodType": "FIXED_COMMITMENT_PERIOD",
                "endDate": end_date,
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
            note="Test handshake",
            relationship_identifier="rel-123456",
            end_date=end_date,
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
            "maxResults": 20,
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
            "maxResults": 20,
        },
        pagination_key="nextToken",
    )


def test_get_channel_handshakes_error(config, aws_client_factory, mock_get_paged_response):
    mock_aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_get_paged_response.side_effect = AWSError("API error")

    with pytest.raises(AWSError, match="API error"):
        mock_aws_client.get_channel_handshakes_by_resource(resource_identifier="rel-123456")

    mock_get_paged_response.assert_called_once()
