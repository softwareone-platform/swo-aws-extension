from requests import HTTPError

from swo_aws_extension.airtable.models import (
    MPAStatusEnum,
    NotificationStatusEnum,
    NotificationTypeEnum,
)
from swo_aws_extension.constants import (
    CRM_EMPTY_ADDITIONAL_INFO,
    CRM_EMPTY_SUMMARY,
    CRM_EMPTY_TITLE,
    CRM_NOTIFICATION_ADDITIONAL_INFO,
    CRM_NOTIFICATION_SUMMARY,
    CRM_NOTIFICATION_TITLE,
    SupportTypesEnum,
)
from swo_aws_extension.flows.jobs.pool_notifications import check_pool_accounts_notifications
from swo_aws_extension.swo_crm_service import ServiceRequest


def test_check_pool_accounts_notifications(
    mocker,
    pool_notification_factory,
    service_request_ticket_factory,
    config,
    mpa_pool_factory,
    service_client,
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool_factory()]
    pool_notification = pool_notification_factory()
    mocked_pool_notification_model.all.side_effect = [
        [pool_notification],
        [],
    ]
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )
    check_pool_accounts_notifications(config)

    service_client.get_service_requests.assert_called_once()
    assert mocked_pool_notification_model.all.call_count == 2


def test_check_pool_notifications_resolved(
    mocker,
    pool_notification_factory,
    service_request_ticket_factory,
    config,
    mpa_pool_factory,
    service_client,
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool_factory()]
    pool_notification = pool_notification_factory()
    mocked_pool_notification_model.all.side_effect = [
        [pool_notification],
        [],
    ]
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
    assert mocked_pool_notification_model.all.call_count == 2


def test_check_pool_notifications_declined(
    mocker,
    pool_notification_factory,
    service_request_ticket_factory,
    config,
    mpa_pool_factory,
    service_client,
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )
    pool_notification = pool_notification_factory()
    mocked_master_payer_account_pool_model.all.return_value = [
        mpa_pool_factory(),
        mpa_pool_factory(country="ES"),
        mpa_pool_factory(status=MPAStatusEnum.ASSIGNED.value),
    ]
    mocked_pool_notification_model.all.side_effect = [
        [pool_notification],
        [],
    ]
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
    assert mocked_pool_notification_model.all.call_count == 2


def test_check_pool_notifications_create_empty(
    mocker, pool_notification_factory, service_request_ticket_factory, config, service_client
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
    pool_notification = pool_notification_factory()
    new_pool_notification_empty = pool_notification_factory(
        status=NotificationStatusEnum.NEW, notification_type=NotificationTypeEnum.EMPTY.value
    )
    mocked_pool_notification_model.all.side_effect = [
        [pool_notification],
        [new_pool_notification_empty],
    ]
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )

    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="Resolved"
    )
    check_pool_accounts_notifications(config)

    assert pool_notification.ticket_state == "Resolved"
    assert mocked_pool_notification_model.all.call_count == 2
    assert mocked_pool_notification_model.all.mock_calls[0].kwargs == {
        "formula": "{Status}!='Done'"
    }
    assert mocked_pool_notification_model.all.mock_calls[1].kwargs == {"formula": "{Status}='New'"}

    assert service_client.create_service_request.call_count == 1
    service_request = ServiceRequest(
        additional_info=CRM_EMPTY_ADDITIONAL_INFO,
        summary=CRM_EMPTY_SUMMARY.format(
            type_of_support=SupportTypesEnum.PARTNER_LED_SUPPORT.value
            if pool_notification.pls_enabled
            else SupportTypesEnum.RESOLD_SUPPORT.value,
            seller_country=pool_notification.country,
        ),
        title=CRM_EMPTY_TITLE.format(region=pool_notification.country),
    )
    assert service_client.create_service_request.mock_calls[0].args == (None, service_request)


def test_check_pool_notifications_create_warning(
    mocker,
    pool_notification_factory,
    service_request_ticket_factory,
    mpa_pool_factory,
    config,
    service_client,
):
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool_factory()]

    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    pool_notification = pool_notification_factory()
    new_pool_notification_warning = pool_notification_factory(
        status=NotificationStatusEnum.NEW.value,
        notification_type=NotificationTypeEnum.WARNING.value,
    )
    mocked_pool_notification_model.all.side_effect = [
        [pool_notification],
        [new_pool_notification_warning],
    ]
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )

    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )

    check_pool_accounts_notifications(config)

    assert pool_notification.ticket_state == "New"
    assert mocked_pool_notification_model.all.call_count == 2
    assert mocked_pool_notification_model.all.mock_calls[0].kwargs == {
        "formula": "{Status}!='Done'"
    }
    assert mocked_pool_notification_model.all.mock_calls[1].kwargs == {"formula": "{Status}='New'"}

    service_request = ServiceRequest(
        additional_info=CRM_NOTIFICATION_ADDITIONAL_INFO,
        summary=CRM_NOTIFICATION_SUMMARY.format(
            type_of_support=SupportTypesEnum.PARTNER_LED_SUPPORT.value
            if pool_notification.pls_enabled
            else SupportTypesEnum.RESOLD_SUPPORT.value,
            seller_country=pool_notification.country,
        ),
        title=CRM_NOTIFICATION_TITLE.format(region=pool_notification.country),
    )
    assert service_client.create_service_request.mock_calls[0].args == (None, service_request)


def test_check_pool_notifications_del_duplicated(
    mocker,
    pool_notification_factory,
    service_request_ticket_factory,
    config,
    mpa_pool_factory,
    service_client,
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool_factory()]
    mocked_pool_notification_model.all.side_effect = [
        [
            pool_notification_factory(status=NotificationStatusEnum.NEW.value, country="FR"),
            pool_notification_factory(status=NotificationStatusEnum.NEW.value, country="FR"),
            pool_notification_factory(status=NotificationStatusEnum.NEW.value),
            pool_notification_factory(),
        ],
        [],
    ]
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )
    check_pool_accounts_notifications(config)

    assert mocked_pool_notification_model.all.call_count == 2
    assert mocked_pool_notification_model.return_value.save.call_count == 1


def test_process_pending_notification_http_error(
    mocker,
    pool_notification_factory,
    service_request_ticket_factory,
    config,
    mpa_pool_factory,
    service_client,
):
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.all.return_value = [
        mpa_pool_factory(),
        mpa_pool_factory(),
        mpa_pool_factory(pls_enabled=False),
        mpa_pool_factory(pls_enabled=False),
    ]

    mocked_pool_notification_model.all.side_effect = [
        [pool_notification_factory(), pool_notification_factory(pls_enabled=False)],
        [],
    ]
    mocker.patch(
        "swo_aws_extension.flows.jobs.pool_notifications.get_service_client",
        return_value=service_client,
    )
    service_client.get_service_requests.side_effect = HTTPError("Test error")
    check_pool_accounts_notifications(config)

    assert mocked_pool_notification_model.return_value.save.call_count == 0
