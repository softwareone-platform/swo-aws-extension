import datetime as dt

from freezegun import freeze_time

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.swo.mpt.sync.apn_client import get_apn_client


def test_get_apn_client_reuses_client(config, mock_apn_client_class):
    get_apn_client()

    get_apn_client()  # act

    assert mock_apn_client_class.call_count == 1


@freeze_time("2026-10-29T12:00:00Z")
def test_get_apn_client_refreshes_expiring_client(mocker, config, mock_apn_client_class):
    expiring_client = mocker.Mock(spec=AWSClient)
    expiring_client.credentials = {"Expiration": dt.datetime.fromisoformat("2026-10-29T12:04:00Z")}
    fresh_client = mocker.Mock(spec=AWSClient)
    fresh_client.credentials = {"Expiration": dt.datetime.fromisoformat("2026-10-29T13:00:00Z")}
    mock_apn_client_class.side_effect = [expiring_client, fresh_client]

    result = get_apn_client()

    assert result is fresh_client


def test_get_apn_client_keeps_client_without_expiration(config, mock_apn_client_class):
    mock_apn_client_class.return_value.credentials = {}
    get_apn_client()

    get_apn_client()  # act

    assert mock_apn_client_class.call_count == 1
