import datetime as dt

import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.aws.models import ServiceTermRenewal
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


@pytest.fixture
def pending_renewal_factory():
    def factory(status="PENDING", period_type="MINIMUM_NOTICE_PERIOD", note=RENEWAL_NOTE):
        return {
            "id": "hs-777777",
            "status": status,
            "detail": {
                "startServicePeriodHandshakeDetail": {
                    "servicePeriodType": period_type,
                    "minimumNoticeDays": "90",
                    "note": note,
                }
            },
        }

    return factory


@pytest.fixture
def renewal_apn_client(mock_apn_client, channel_handshake_factory):
    mock_apn_client.get_channel_handshakes_by_resource.return_value = [channel_handshake_factory()]
    mock_apn_client.get_program_management_id_by_account.return_value = "pm-123456"
    mock_apn_client.create_channel_handshake.return_value = {
        "channelHandshakeDetail": {"id": "hs-654321"}
    }
    return mock_apn_client


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


def test_send_service_term_renewal(config, renewal_apn_client):
    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert result == ServiceTermRenewal("hs-654321", is_accepted=False)


def test_send_service_term_renewal_sends_minimum_notice_term(mocker, config, renewal_apn_client):
    send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")  # act

    assert (
        renewal_apn_client.get_channel_handshakes_by_resource.call_args_list,
        renewal_apn_client.get_program_management_id_by_account.call_args_list,
        renewal_apn_client.create_channel_handshake.call_args_list,
    ) == (
        [mocker.call("rel-123456")],
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


@pytest.mark.parametrize(("status", "is_accepted"), [("PENDING", False), ("ACCEPTED", True)])
def test_send_service_term_renewal_reuses_sent_renewal(
    config,
    renewal_apn_client,
    channel_handshake_factory,
    pending_renewal_factory,
    status,
    is_accepted,
):
    renewal_apn_client.get_channel_handshakes_by_resource.return_value = [
        channel_handshake_factory(),
        pending_renewal_factory(status=status),
    ]

    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert (result, renewal_apn_client.create_channel_handshake.called) == (
        ServiceTermRenewal("hs-777777", is_accepted=is_accepted),
        False,
    )


@pytest.mark.parametrize(
    "handshake_changes",
    [
        {"status": "EXPIRED"},
        {"status": "REJECTED"},
        {"period_type": "FIXED_COMMITMENT_PERIOD"},
        {"note": "Please accept your Service Terms contract with SoftwareOne"},
        {"note": RENEWAL_NOTE.replace(AGREEMENT_ID, "AGR-0000-0000-0000-0000")},
    ],
)
def test_send_service_term_renewal_ignores_other_handshakes(
    config, renewal_apn_client, pending_renewal_factory, handshake_changes
):
    renewal_apn_client.get_channel_handshakes_by_resource.return_value = [
        pending_renewal_factory(**handshake_changes)
    ]

    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert (result, renewal_apn_client.create_channel_handshake.call_count) == (
        ServiceTermRenewal("hs-654321", is_accepted=False),
        1,
    )


def test_send_service_term_renewal_without_program_management_account(
    mocker, config, renewal_apn_client, mock_send_warning
):
    renewal_apn_client.get_program_management_id_by_account.return_value = ""

    result = send_service_term_renewal(AGREEMENT_ID, "651706759263", "rel-123456")

    assert (
        result,
        renewal_apn_client.create_channel_handshake.called,
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
    "failing_call",
    [
        "get_channel_handshakes_by_resource",
        "get_program_management_id_by_account",
        "create_channel_handshake",
    ],
)
def test_send_service_term_renewal_aws_error(
    mocker, config, renewal_apn_client, mock_send_exception, failing_call
):
    getattr(renewal_apn_client, failing_call).side_effect = AWSError("access denied")

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
