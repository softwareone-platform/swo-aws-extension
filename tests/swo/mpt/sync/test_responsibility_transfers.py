import datetime as dt

import pytest

from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.swo.mpt.sync.responsibility_transfers import (
    get_available_responsibility_transfers,
    get_available_transfer_for_account,
)


@pytest.fixture(autouse=True)
def clear_function_cache():
    """Clear cache for cached functions between tests."""
    yield
    get_available_responsibility_transfers.cache_clear()


def test_get_available_transfers_success(config, mock_awsclient, responsibility_transfer_factory):
    pma_account_id = "123456789012"
    withdrawn_end = "2026-10-31T23:59:59+00:00"
    transfers = [
        responsibility_transfer_factory(
            source="225989344502", status=ResponsibilityTransferStatus.ACCEPTED.value
        ),
        responsibility_transfer_factory(
            source="651706759263", status=ResponsibilityTransferStatus.REQUESTED.value
        ),
        responsibility_transfer_factory(
            source="651706759264", status=ResponsibilityTransferStatus.DECLINED.value
        ),
        responsibility_transfer_factory(
            source="651706759265",
            status=ResponsibilityTransferStatus.WITHDRAWN.value,
            end_timestamp=withdrawn_end,
        ),
    ]
    mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

    result = get_available_responsibility_transfers(pma_account_id)  # act

    assert result == {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
            "EndTimestamp": None,
        },
        "651706759265": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.WITHDRAWN.value,
            "EndTimestamp": dt.datetime.fromisoformat(withdrawn_end),
        },
    }
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_available_transfers_multiple_withdrawn_keeps_latest(
    config, mock_awsclient, responsibility_transfer_factory
):
    pma_account_id = "123456789012"
    withdrawn = ResponsibilityTransferStatus.WITHDRAWN.value
    transfers = [
        responsibility_transfer_factory(transfer_id="rt-no-end", status=withdrawn),
        responsibility_transfer_factory(
            transfer_id="rt-old",
            status=withdrawn,
            end_timestamp="2026-06-30T23:59:59+00:00",
        ),
        responsibility_transfer_factory(
            transfer_id="rt-latest",
            status=withdrawn,
            end_timestamp="2026-10-31T23:59:59+00:00",
        ),
        responsibility_transfer_factory(
            transfer_id="rt-mid",
            status=withdrawn,
            end_timestamp="2026-08-31T23:59:59+00:00",
        ),
    ]
    mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

    result = get_available_responsibility_transfers(pma_account_id)  # act

    assert result == {
        "225989344502": {
            "Id": "rt-latest",
            "Status": withdrawn,
            "EndTimestamp": dt.datetime.fromisoformat("2026-10-31T23:59:59+00:00"),
        },
    }


@pytest.mark.parametrize("accepted_first", [True, False])
def test_get_available_transfers_accepted_wins(
    config, mock_awsclient, responsibility_transfer_factory, accepted_first
):
    pma_account_id = "123456789012"
    accepted = responsibility_transfer_factory(
        transfer_id="rt-accepted", status=ResponsibilityTransferStatus.ACCEPTED.value
    )
    withdrawn = responsibility_transfer_factory(
        transfer_id="rt-withdrawn",
        status=ResponsibilityTransferStatus.WITHDRAWN.value,
        end_timestamp="2026-10-31T23:59:59+00:00",
    )
    transfers = [accepted, withdrawn] if accepted_first else [withdrawn, accepted]
    mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

    result = get_available_responsibility_transfers(pma_account_id)  # act

    assert result["225989344502"]["Id"] == "rt-accepted"


def test_get_available_transfers_empty(config, mock_awsclient, responsibility_transfer_factory):
    pma_account_id = "123456789012"
    mock_awsclient.get_inbound_responsibility_transfers.return_value = []

    result = get_available_responsibility_transfers(pma_account_id)

    assert result == {}
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_available_transfers_error(config, mock_awsclient):
    pma_account_id = "123456789012"
    mock_awsclient.get_inbound_responsibility_transfers.side_effect = Exception("Error occurred")

    with pytest.raises(Exception, match="Error occurred"):
        get_available_responsibility_transfers(pma_account_id)

    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_available_transfers_all_inactive(
    config, mock_awsclient, responsibility_transfer_factory
):
    pma_account_id = "123456789012"
    transfers = [
        responsibility_transfer_factory(
            source="source1", status=ResponsibilityTransferStatus.DECLINED.value
        ),
        responsibility_transfer_factory(
            source="source2", status=ResponsibilityTransferStatus.CANCELED.value
        ),
        responsibility_transfer_factory(
            source="source3", status=ResponsibilityTransferStatus.EXPIRED.value
        ),
        responsibility_transfer_factory(
            source="source4", status=ResponsibilityTransferStatus.REQUESTED.value
        ),
    ]
    mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

    result = get_available_responsibility_transfers(pma_account_id)

    assert result == {}
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_available_transfers_no_source(config, mock_awsclient, responsibility_transfer_factory):
    pma_account_id = "123456789012"
    transfer_with_source = responsibility_transfer_factory(
        source="225989344502", status=ResponsibilityTransferStatus.ACCEPTED.value
    )
    transfer_without_source = {
        "Id": "rt-nosource",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        "Target": {"ManagementAccountId": "651706759263"},
    }
    mock_awsclient.get_inbound_responsibility_transfers.return_value = [
        transfer_with_source,
        transfer_without_source,
    ]

    result = get_available_responsibility_transfers(pma_account_id)

    assert result == {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
            "EndTimestamp": None,
        },
    }


def test_get_transfer_for_account_found(
    mock_get_responsibility_transfers,
):
    mock_get_responsibility_transfers.return_value = {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        },
    }

    result = get_available_transfer_for_account("651706759263", "225989344502")

    assert result == {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }


def test_get_transfer_for_account_not_found(
    mock_get_responsibility_transfers,
):
    mock_get_responsibility_transfers.return_value = {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        },
    }

    result = get_available_transfer_for_account("651706759263", "999999999999")

    assert result is None
