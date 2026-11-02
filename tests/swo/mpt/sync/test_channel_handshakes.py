import datetime as dt

import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS
from swo_aws_extension.swo.mpt.sync.channel_handshakes import (
    get_fixed_commitment_end_date,
    send_service_term_renewal,
)

AGREEMENT_ID = "AGR-2119-4550-8674-5962"
RENEWAL_NOTE = (
    "Dear customer, your initial service term for Agreement AGR-2119-4550-8674-5962 has "
    "expired, hence we are sending a new up to date service term. By accepting this service "
    "term both parties provide mutual consent to maintain the current billing relationship "
    "active and to prevent unilateral changes to it within the defined period."
)


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


def test_send_service_term_renewal(config, mock_apn_client):
    mock_apn_client.get_program_management_id_by_account.return_value = "pm-123456"
    mock_apn_client.create_channel_handshake.return_value = {
        "channelHandshakeDetail": {"id": "hs-654321"}
    }

    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert result == "hs-654321"


def test_send_service_term_renewal_sends_minimum_notice_term(mocker, config, mock_apn_client):
    mock_apn_client.get_program_management_id_by_account.return_value = "pm-123456"
    mock_apn_client.create_channel_handshake.return_value = {
        "channelHandshakeDetail": {"id": "hs-654321"}
    }

    send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")  # act

    assert (
        mock_apn_client.get_program_management_id_by_account.call_args_list,
        mock_apn_client.create_channel_handshake.call_args_list,
    ) == (
        [mocker.call("651706759263")],
        [
            mocker.call(
                pma_identifier="pm-123456",
                relationship_identifier="rel-123456",
                minimum_notice_days=CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS,
                note=RENEWAL_NOTE,
            )
        ],
    )


def test_send_service_term_renewal_without_program_management_account(
    mocker, config, mock_apn_client, mock_send_warning
):
    mock_apn_client.get_program_management_id_by_account.return_value = ""

    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert (
        result,
        mock_apn_client.create_channel_handshake.called,
        mock_send_warning.call_args_list,
    ) == (
        None,
        False,
        [
            mocker.call(
                f"{AGREEMENT_ID} - Service term renewal",
                "Program management account not found for account 651706759263",
            )
        ],
    )


@pytest.mark.parametrize(
    ("program_management_lookup", "handshake_creation"),
    [
        ({"side_effect": AWSError("access denied")}, {}),
        ({"return_value": "pm-123456"}, {"side_effect": AWSError("access denied")}),
    ],
)
def test_send_service_term_renewal_aws_error(
    mocker,
    config,
    mock_apn_client,
    mock_send_exception,
    program_management_lookup,
    handshake_creation,
):
    mock_apn_client.get_program_management_id_by_account.configure_mock(**program_management_lookup)
    mock_apn_client.create_channel_handshake.configure_mock(**handshake_creation)

    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert (result, mock_send_exception.call_args_list) == (
        None,
        [
            mocker.call(
                f"{AGREEMENT_ID} - Service term renewal",
                "Failed to send the new service term for relationship rel-123456: access denied",
            )
        ],
    )
