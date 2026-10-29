import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.swo.mpt.sync.channel_handshakes import get_fixed_commitment_end_date

AGREEMENT_ID = "AGR-2119-4550-8674-5962"


def test_get_fixed_commitment_end_date(config, mock_apn_client, channel_handshake_factory):
    mock_apn_client.get_channel_handshake_by_id.return_value = channel_handshake_factory()

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert result == dt.date.fromisoformat("2027-02-01")


def test_get_fixed_commitment_end_date_reads_handshake(
    config, mock_apn_client, channel_handshake_factory
):
    mock_apn_client.get_channel_handshake_by_id.return_value = channel_handshake_factory()

    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")  # act

    mock_apn_client.get_channel_handshake_by_id.assert_called_once_with("rel-123456", "hs-123456")


def test_get_fixed_commitment_end_date_not_fixed(
    config, mock_apn_client, channel_handshake_factory
):
    mock_apn_client.get_channel_handshake_by_id.return_value = channel_handshake_factory(
        period_type="MINIMUM_NOTICE_PERIOD"
    )

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert result is None


@pytest.mark.parametrize(
    "handshake_lookup",
    [
        {"return_value": None},
        {"side_effect": AWSError("access denied")},
    ],
)
def test_get_fixed_commitment_end_date_handshake_unavailable(
    config, mock_apn_client, mock_send_warning, handshake_lookup
):
    mock_apn_client.get_channel_handshake_by_id.configure_mock(**handshake_lookup)

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert result is None


@pytest.mark.parametrize(
    "handshake",
    [
        {"id": "hs-123456", "status": "ACCEPTED", "detail": None},
        {
            "id": "hs-123456",
            "status": "ACCEPTED",
            "detail": {"startServicePeriodHandshakeDetail": {"endDate": "bad"}},
        },
    ],
)
def test_get_fixed_commitment_end_date_malformed_handshake(config, mock_apn_client, handshake):
    mock_apn_client.get_channel_handshake_by_id.return_value = handshake

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert result is None


@pytest.mark.parametrize("status", ["PENDING", "REJECTED", "CANCELED"])
def test_get_fixed_commitment_end_date_not_accepted(
    config, mock_apn_client, channel_handshake_factory, status
):
    handshake = {**channel_handshake_factory(), "status": status}
    mock_apn_client.get_channel_handshake_by_id.return_value = handshake

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert result is None


def test_get_fixed_commitment_end_date_without_end_date(config, mock_apn_client, mock_send_warning):
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": "ACCEPTED",
        "detail": {
            "startServicePeriodHandshakeDetail": {"servicePeriodType": "FIXED_COMMITMENT_PERIOD"}
        },
    }

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert result is None


def test_get_fixed_commitment_end_date_reuses_apn_client(
    config, mock_apn_client_class, channel_handshake_factory
):
    mock_apn_client_class.return_value.get_channel_handshake_by_id.return_value = (
        channel_handshake_factory()
    )
    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-111111", "hs-111111")

    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-222222", "hs-222222")  # act

    assert mock_apn_client_class.call_count == 1


@freeze_time("2026-10-29T12:00:00Z")
def test_get_fixed_commitment_end_date_refreshes_expiring_client(
    mocker, config, mock_apn_client_class, channel_handshake_factory
):
    expiring_client = mocker.Mock(spec=AWSClient)
    expiring_client.credentials = {"Expiration": dt.datetime.fromisoformat("2026-10-29T12:04:00Z")}
    fresh_client = mocker.Mock(spec=AWSClient)
    fresh_client.credentials = {"Expiration": dt.datetime.fromisoformat("2026-10-29T13:00:00Z")}
    fresh_client.get_channel_handshake_by_id.return_value = channel_handshake_factory()
    mock_apn_client_class.side_effect = [expiring_client, fresh_client]

    result = get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")

    assert (result, expiring_client.get_channel_handshake_by_id.called) == (
        dt.date.fromisoformat("2027-02-01"),
        False,
    )


def test_get_fixed_commitment_end_date_keeps_client_without_expiration(
    config, mock_apn_client_class, channel_handshake_factory
):
    mock_apn_client_class.return_value.credentials = {}
    mock_apn_client_class.return_value.get_channel_handshake_by_id.return_value = (
        channel_handshake_factory()
    )
    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-111111", "hs-111111")

    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-222222", "hs-222222")  # act

    assert mock_apn_client_class.call_count == 1


def test_get_fixed_commitment_end_date_logs_invalid_end_date_as_warning(
    caplog, config, mock_apn_client, channel_handshake_factory
):
    handshake = channel_handshake_factory()
    handshake["detail"]["startServicePeriodHandshakeDetail"]["endDate"] = "not-a-date"
    mock_apn_client.get_channel_handshake_by_id.return_value = handshake

    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")  # act

    assert [
        (record.levelname, record.exc_info is None, "not-a-date" in record.getMessage())
        for record in caplog.records
    ] == [("WARNING", True, True)]


@pytest.mark.parametrize(
    ("handshake", "expected_message"),
    [
        (None, "Channel handshake hs-123456 not found for relationship rel-123456"),
        (
            {
                "id": "hs-123456",
                "status": "ACCEPTED",
                "detail": {
                    "startServicePeriodHandshakeDetail": {
                        "servicePeriodType": "FIXED_COMMITMENT_PERIOD"
                    }
                },
            },
            "Channel handshake hs-123456 has a fixed commitment period without an end date",
        ),
    ],
)
def test_get_fixed_commitment_end_date_warns_on_teams(
    mocker, caplog, config, mock_apn_client, mock_send_warning, handshake, expected_message
):
    mock_apn_client.get_channel_handshake_by_id.return_value = handshake

    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")  # act

    assert (
        [(record.levelname, record.getMessage()) for record in caplog.records],
        mock_send_warning.call_args_list,
    ) == (
        [("WARNING", expected_message)],
        [mocker.call(f"{AGREEMENT_ID} - Synchronize handshake expiration date", expected_message)],
    )


@pytest.mark.parametrize(
    "handshake_lookup",
    [
        {"side_effect": AWSError("access denied")},
        {"return_value": {"id": "hs-123456", "status": "PENDING"}},
    ],
)
def test_get_fixed_commitment_end_date_no_teams_warning(
    config, mock_apn_client, mock_send_warning, handshake_lookup
):
    mock_apn_client.get_channel_handshake_by_id.configure_mock(**handshake_lookup)

    get_fixed_commitment_end_date(AGREEMENT_ID, "rel-123456", "hs-123456")  # act

    mock_send_warning.assert_not_called()
