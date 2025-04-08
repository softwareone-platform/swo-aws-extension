from swo_aws_extension.constants import (
    EMPTY_SUMMARY,
    EMPTY_TITLE,
    NOTIFICATION_SUMMARY,
    NOTIFICATION_TITLE,
)
from swo_aws_extension.flows.jobs.pool_notifications import check_pool_accounts_notifications
from swo_crm_service_client import CRMServiceClient, ServiceRequest


def test_check_pool_accounts_notifications(
    mocker, pool_notification, service_request_ticket_factory, config
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )

    mocked_pool_notification_model.all.return_value = [pool_notification]
    mocked_pool_notification_model.first.return_value = pool_notification
    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )
    check_pool_accounts_notifications(config)

    service_client.get_service_requests.assert_called_once()
    assert mocked_pool_notification_model.all.call_count == 1
    assert mocked_pool_notification_model.first.call_count == 2


def test_check_pool_accounts_notifications_resolved(
    mocker, pool_notification, service_request_ticket_factory, config
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )

    mocked_pool_notification_model.all.return_value = [pool_notification]
    mocked_pool_notification_model.first.return_value = pool_notification
    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="Resolved"
    )
    check_pool_accounts_notifications(config)

    service_client.get_service_requests.assert_called_once()
    assert pool_notification.ticket_state == "Resolved"
    pool_notification.save.assert_called_once()
    assert mocked_pool_notification_model.all.call_count == 1
    assert mocked_pool_notification_model.first.call_count == 2


def test_check_pool_accounts_notifications_declined(
    mocker, pool_notification, service_request_ticket_factory, config
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )

    mocked_pool_notification_model.all.return_value = [pool_notification]
    mocked_pool_notification_model.first.return_value = pool_notification
    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="Declined"
    )
    check_pool_accounts_notifications(config)

    service_client.get_service_requests.assert_called_once()
    assert pool_notification.ticket_state == "Declined"
    pool_notification.save.assert_called_once()
    assert mocked_pool_notification_model.all.call_count == 1
    assert mocked_pool_notification_model.first.call_count == 2


def test_check_pool_accounts_notifications_create_empty_notification(
    mocker, pool_notification, service_request_ticket_factory, config
):
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = []

    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )

    mocked_pool_notification_model.all.return_value = []
    mocked_pool_notification_model.first.return_value = ""
    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )

    service_client.create_service_request.return_value = {"id": "1234-5678"}
    check_pool_accounts_notifications(config)

    assert pool_notification.ticket_state == "New"
    assert mocked_pool_notification_model.all.call_count == 1
    assert mocked_pool_notification_model.first.call_count == 2
    assert mocked_pool_notification_model.all.mock_calls[0].kwargs == {
        "formula": "{Status}='Pending'"
    }
    assert mocked_pool_notification_model.first.call_args_list[0].kwargs == {
        "formula": "AND({PLS Enabled},{Status}='Pending')"
    }
    assert mocked_pool_notification_model.first.call_args_list[1].kwargs == {
        "formula": "AND(NOT({PLS Enabled}),{Status}='Pending')"
    }
    assert mocked_pool_notification_model.return_value.save.call_count == 2

    assert service_client.create_service_request.call_count == 2
    service_request = ServiceRequest(
        external_user_email="test@example.com",
        external_username="test@example.com",
        requester="Supplier.Portal",
        sub_service="Service Activation",
        global_academic_ext_user_id="globalacademicExtUserId",
        additional_info="AWS Master Payer account",
        summary=EMPTY_SUMMARY,
        title=EMPTY_TITLE,
        service_type="MarketPlaceServiceActivation",
    )
    assert service_client.create_service_request.mock_calls[0].args == (None, service_request)
    assert service_client.create_service_request.mock_calls[1].args == (None, service_request)


def test_check_pool_accounts_notifications_create_warning_notification(
    mocker, pool_notification, service_request_ticket_factory, mpa_pool, config
):
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool]

    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )

    mocked_pool_notification_model.all.return_value = []
    mocked_pool_notification_model.first.return_value = ""
    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )

    service_client.create_service_request.return_value = {"id": "1234-5678"}
    check_pool_accounts_notifications(config)

    assert pool_notification.ticket_state == "New"
    assert mocked_pool_notification_model.all.call_count == 1
    assert mocked_pool_notification_model.first.call_count == 2
    assert mocked_pool_notification_model.all.mock_calls[0].kwargs == {
        "formula": "{Status}='Pending'"
    }
    assert mocked_pool_notification_model.first.call_args_list[0].kwargs == {
        "formula": "AND({PLS Enabled},{Status}='Pending')"
    }
    assert mocked_pool_notification_model.first.call_args_list[1].kwargs == {
        "formula": "AND(NOT({PLS Enabled}),{Status}='Pending')"
    }
    assert mocked_pool_notification_model.return_value.save.call_count == 2

    service_request = ServiceRequest(
        external_user_email="test@example.com",
        external_username="test@example.com",
        requester="Supplier.Portal",
        sub_service="Service Activation",
        global_academic_ext_user_id="globalacademicExtUserId",
        additional_info="AWS Master Payer account",
        summary=NOTIFICATION_SUMMARY,
        title=NOTIFICATION_TITLE,
        service_type="MarketPlaceServiceActivation",
    )
    assert service_client.create_service_request.mock_calls[0].args == (None, service_request)
    assert service_client.create_service_request.mock_calls[1].args == (None, service_request)


def test_check_pool_accounts_notifications_not_create_notification(
    mocker, pool_notification, service_request_ticket_factory, mpa_pool, config
):
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [
        mpa_pool,
        mpa_pool,
        mpa_pool,
        mpa_pool,
    ]

    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )

    mocked_pool_notification_model.all.return_value = []
    mocked_pool_notification_model.first.return_value = pool_notification
    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )

    service_client.create_service_request.return_value = {"id": "1234-5678"}
    check_pool_accounts_notifications(config)

    assert pool_notification.ticket_state == "New"
    assert mocked_pool_notification_model.all.call_count == 1
    assert mocked_pool_notification_model.first.call_count == 2
    assert mocked_pool_notification_model.all.mock_calls[0].kwargs == {
        "formula": "{Status}='Pending'"
    }
    assert mocked_pool_notification_model.first.call_args_list[0].kwargs == {
        "formula": "AND({PLS Enabled},{Status}='Pending')"
    }
    assert mocked_pool_notification_model.first.call_args_list[1].kwargs == {
        "formula": "AND(NOT({PLS Enabled}),{Status}='Pending')"
    }
