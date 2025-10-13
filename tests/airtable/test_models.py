from requests import HTTPError

from swo_aws_extension.airtable.models import (
    NotificationStatusEnum,
    get_available_mpa_from_pool,
    get_master_payer_account_pool_model,
    get_mpa_account,
    get_mpa_view_link,
    get_notifications_by_status,
    get_open_notifications,
    get_pool_notification_model,
)


def test_get_master_payer_account_pool_model(base_info):
    master_payer_account_pool = get_master_payer_account_pool_model(base_info)

    record = master_payer_account_pool(
        account_id="Account Id",
        account_email="Account Email",
        account_name="Account Name",
        pls_enabled=True,
        status="Status",
        agreement_id="Agreement Id",
        client_id="Client Id",
        scu="SCU",
    )

    assert record.account_id == "Account Id"
    assert record.account_email == "Account Email"
    assert record.account_name == "Account Name"
    assert record.pls_enabled
    assert record.status == "Status"
    assert record.agreement_id == "Agreement Id"
    assert record.client_id == "Client Id"
    assert record.scu == "SCU"


def test_get_pool_notification_model(base_info):
    pool_notification_model = get_pool_notification_model(base_info)

    record = pool_notification_model(
        notification_type="Notification Type",
        pls_enabled=True,
        ticket_id="Ticket Id",
        ticket_state="Ticket State",
        status="Status",
    )

    assert record.ticket_id == "Ticket Id"
    assert record.ticket_state == "Ticket State"
    assert record.status == "Status"
    assert record.notification_type == "Notification Type"
    assert record.pls_enabled


def test_get_available_mpa_from_pool(mocker, base_info, mpa_pool_factory):
    mock_mpa_pool = mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model"
    )
    mpa_pool = mpa_pool_factory()
    mock_mpa_pool.return_value.all.return_value = [mpa_pool]

    available_mpa = get_available_mpa_from_pool()

    assert available_mpa == [mpa_pool]
    mock_mpa_pool.assert_called_once_with(base_info)
    mock_mpa_pool.return_value.all.assert_called_once()


def test_get_pending_notifications(mocker, base_info, pool_notification_factory):
    mock_pool_notification = mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model"
    )
    pool_notification = pool_notification_factory()
    pool_notification.status = NotificationStatusEnum.PENDING.value
    mock_pool_notification.return_value.all.return_value = [pool_notification]

    notifications = get_notifications_by_status(NotificationStatusEnum.PENDING.value)

    assert notifications == [pool_notification]
    assert notifications[0].status == NotificationStatusEnum.PENDING.value
    mock_pool_notification.assert_called_once_with(base_info)
    mock_pool_notification.return_value.all.assert_called_once()


def test_get_open_notifications(mocker, base_info, pool_notification_factory):
    mock_pool_notification = mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model"
    )
    mock_pool_notification.return_value.all.return_value = [pool_notification_factory()]

    notifications = get_open_notifications()

    assert notifications
    mock_pool_notification.assert_called_once_with(base_info)
    mock_pool_notification.return_value.all.assert_called_once()


def test_get_mpa_view_link(mocker, base_info):
    mock_mpa_pool = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mock_mpa_pool,
    )
    mock_mpa_pool.id = "record-id"
    mock_mpa_pool.Meta.base_id = "base-id"
    view_mock = mocker.MagicMock()
    view_mock.id = "view-id"
    schema_mock = mocker.MagicMock()
    schema_mock.view.return_value = view_mock
    table_mock = mocker.MagicMock()
    table_mock.id = "table-id"
    table_mock.schema.return_value = schema_mock
    mock_mpa_pool.get_table.return_value = table_mock

    view_link = get_mpa_view_link()

    assert view_link == "https://airtable.com/base-id/table-id/view-id/record-id"


def test_get_mpa_view_link_error(mocker, base_info):
    mock_mpa_pool = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mock_mpa_pool,
    )

    mock_mpa_pool.get_table.side_effect = HTTPError()

    assert get_mpa_view_link() is None


def test_get_mpa_account(mocker, base_info, mpa_pool_factory):
    master_payer_account_pool = mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model"
    )

    master_payer_account_pool.return_value.first.return_value = mpa_pool_factory()

    assert get_mpa_account("Account Id")
    master_payer_account_pool.assert_called_once_with(base_info)
    master_payer_account_pool.return_value.first.assert_called_once()
