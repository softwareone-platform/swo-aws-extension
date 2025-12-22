from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.flows.jobs.process_aws_invitations import AWSInvitationsProcessor

MPT_BASE_URL = "https://localhost"
ORDERS_URL = (
    f"{MPT_BASE_URL}/v1/commerce/orders?"
    "and(in(agreement.product.id,(PRD-1111-1111)),eq(status,Querying))"
    "&select=audit,parameters,lines,subscriptions,subscriptions.lines,agreement,buyer"
    "&order=audit.created.at&limit=10&offset=0"
)


def test_process_invitations_status_changed(
    mocker, mpt_client, config, order_factory, fulfillment_parameters_factory, requests_mocker
):
    """Test processing when transfer status has changed from REQUESTED."""
    processor = AWSInvitationsProcessor(mpt_client, config)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-test-123"
        )
    )
    requests_mocker.add(
        requests_mocker.GET,
        ORDERS_URL,
        json={
            "data": [order],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    mock_aws_client = mocker.MagicMock()
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.process_aws_invitations.AWSClient",
        return_value=mock_aws_client,
    )
    switch_order_mock = mocker.patch(
        "swo_aws_extension.flows.jobs.process_aws_invitations."
        "switch_order_status_to_process_and_notify"
    )

    processor.process_aws_invitations()  # act

    mock_aws_client.get_responsibility_transfer_details.assert_called_once_with(
        transfer_id="rt-test-123"
    )
    switch_order_mock.assert_called_once()


def test_process_invitations_still_requested(
    mocker, config, mpt_client, order_factory, fulfillment_parameters_factory, requests_mocker
):
    """Test processing when transfer is still in REQUESTED status."""
    processor = AWSInvitationsProcessor(mpt_client, config)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-test-123"
        )
    )
    requests_mocker.add(
        requests_mocker.GET,
        ORDERS_URL,
        json={
            "data": [order],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    mock_aws_client = mocker.MagicMock()
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.REQUESTED}
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.process_aws_invitations.AWSClient",
        return_value=mock_aws_client,
    )

    processor.process_aws_invitations()  # act

    mock_aws_client.get_responsibility_transfer_details.assert_called_once_with(
        transfer_id="rt-test-123"
    )


def test_process_invitations_aws_error(
    mocker, config, mpt_client, order_factory, fulfillment_parameters_factory, requests_mocker
):
    """Test processing when AWS error occurs."""
    processor = AWSInvitationsProcessor(mpt_client, config)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-test-123"
        )
    )
    requests_mocker.add(
        requests_mocker.GET,
        ORDERS_URL,
        json={
            "data": [order],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    mock_aws_client = mocker.MagicMock()
    mock_aws_client.get_responsibility_transfer_details.side_effect = AWSError("AWS API error")
    mocker.patch(
        "swo_aws_extension.flows.jobs.process_aws_invitations.AWSClient",
        return_value=mock_aws_client,
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.jobs.process_aws_invitations.TeamsNotificationManager"
    )

    processor.process_aws_invitations()  # act

    notification_mock.return_value.notify_one_time_error.assert_called_once()


def test_process_invitations_no_orders(mocker, config, mpt_client, requests_mocker):
    """Test processing when there are no querying orders."""
    processor = AWSInvitationsProcessor(mpt_client, config)
    requests_mocker.add(
        requests_mocker.GET,
        ORDERS_URL,
        json={
            "data": [],
            "$meta": {"pagination": {"total": 0, "limit": 10, "offset": 0}},
        },
    )

    processor.process_aws_invitations()  # act

    assert len(requests_mocker.calls) == 1
