from requests import HTTPError

from swo_aws_extension.airtable.models import (
    NotificationStatusEnum,
    get_available_mpa_from_pool,
    get_in_progress_notifications,
    get_master_payer_account_pool_model,
    get_mpa_view_link,
    get_pending_notifications,
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
        notification_id=1,
        notification_type="Notification Type",
        pls_enabled=True,
        ticket_id="Ticket Id",
        ticket_status="Ticket Status",
        status="Status",
    )

    assert record.ticket_id == "Ticket Id"
    assert record.ticket_status == "Ticket Status"
    assert record.status == "Status"
    assert record.notification_id == 1
    assert record.notification_type == "Notification Type"
    assert record.pls_enabled


def test_get_available_mpa_from_pool(mocker, base_info, mpa_pool):
    mock_mpa_pool = mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model"
    )
    mock_mpa_pool.return_value.all.return_value = [mpa_pool]
    result = get_available_mpa_from_pool(pls_enabled=True)
    assert result == [mpa_pool]
    mock_mpa_pool.assert_called_once_with(base_info)
    mock_mpa_pool.return_value.all.assert_called_once()


def test_get_pending_notifications(mocker, base_info, pool_notification):
    mock_pool_notification = mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model"
    )
    pool_notification.status = NotificationStatusEnum.PENDING
    mock_pool_notification.return_value.all.return_value = [pool_notification]
    result = get_pending_notifications()
    assert result == [pool_notification]
    assert result[0].status == NotificationStatusEnum.PENDING
    mock_pool_notification.assert_called_once_with(base_info)
    mock_pool_notification.return_value.all.assert_called_once()


def test_get_in_progress_notifications(mocker, base_info, pool_notification):
    mock_pool_notification = mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model"
    )
    mock_pool_notification.return_value.all.return_value = [pool_notification]
    result = get_in_progress_notifications()
    assert result == [pool_notification]
    assert result[0].status == NotificationStatusEnum.IN_PROGRESS
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

    assert get_mpa_view_link() == "https://airtable.com/base-id/table-id/view-id/record-id"


def test_get_mpa_view_link_error(mocker, base_info):
    mock_mpa_pool = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mock_mpa_pool,
    )
    mock_mpa_pool.get_table.side_effect = HTTPError()

    assert get_mpa_view_link() is None
