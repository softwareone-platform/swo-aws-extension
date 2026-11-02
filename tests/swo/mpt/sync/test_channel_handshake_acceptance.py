import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.swo.mpt.sync.channel_handshake_acceptance import (
    is_channel_handshake_accepted,
)


@pytest.mark.parametrize(
    ("handshake_lookup", "expected_accepted"),
    [
        ({"return_value": {"id": "hs-123456", "status": "ACCEPTED"}}, True),
        ({"return_value": {"id": "hs-123456", "status": "PENDING"}}, False),
        ({"return_value": {"id": "hs-123456", "status": "REJECTED"}}, False),
        ({"return_value": None}, False),
        ({"side_effect": AWSError("access denied")}, False),
    ],
)
def test_is_channel_handshake_accepted(
    config, mock_apn_client, handshake_lookup, expected_accepted
):
    mock_apn_client.get_channel_handshake_by_id.configure_mock(**handshake_lookup)

    result = is_channel_handshake_accepted("rel-123456", "hs-123456")

    assert result is expected_accepted


def test_is_channel_handshake_accepted_reads_handshake(config, mock_apn_client):
    mock_apn_client.get_channel_handshake_by_id.return_value = None

    is_channel_handshake_accepted("rel-123456", "hs-123456")  # act

    mock_apn_client.get_channel_handshake_by_id.assert_called_once_with("rel-123456", "hs-123456")
