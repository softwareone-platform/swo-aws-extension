import pytest

from swo_aws_extension.constants import (
    ResponsibilityTransferStatus,
)
from swo_aws_extension.swo.mpt.sync.syncer import (
    get_accepted_inbound_responsibility_transfers,
    get_accepted_transfer_for_account,
    sync_responsibility_transfer_id,
    synchronize_agreements,
    terminate_agreement,
)


@pytest.fixture(autouse=True)
def clear_function_cache():
    """Clear cache for cached functions between tests."""
    yield
    get_accepted_inbound_responsibility_transfers.cache_clear()


def test_synchronize_agreements_with_specific_ids(
    mpt_client,
    config,
    agreement,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_get_accepted_transfer_for_account,
    mock_sync_responsibility_transfer_id,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_accepted_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_get_accepted_transfer_for_account.call_count == 1
    mock_get_accepted_transfer_for_account.assert_called_once_with("651706759263", "225989344502")
    mock_sync_responsibility_transfer_id.assert_called_once_with(
        mpt_client, agreement, "rt-8lr3q6sn", dry_run=False
    )


def test_synchronize_agreements_without_ids(
    mpt_client,
    config,
    agreement,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_get_accepted_transfer_for_account,
    mock_sync_responsibility_transfer_id,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_accepted_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    synchronize_agreements(mpt_client, [], ["PROD-123-456"], dry_run=False)  # act

    assert mock_get_accepted_transfer_for_account.call_count == 1
    mock_get_accepted_transfer_for_account.assert_called_once_with("651706759263", "225989344502")
    mock_sync_responsibility_transfer_id.assert_called_once_with(
        mpt_client, agreement, "rt-8lr3q6sn", dry_run=False
    )


def test_synchronize_agreements_missing_mpa_account(
    mpt_client,
    config,
    agreement_factory,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_send_error,
    mock_get_accepted_transfer_for_account,
):
    mock_agreement = agreement_factory(vendor_id="")
    mock_get_agreements_by_query.return_value = [mock_agreement]

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_send_error.call_count == 1
    mock_send_error.assert_called_once_with(
        "Synchronize AWS agreement subscriptions",
        f"{mock_agreement.get('id')} - Skipping - MPA not found",
    )
    mock_get_accepted_transfer_for_account.assert_not_called()


def test_synchronize_agreements_missing_pma_account(
    mpt_client,
    config,
    agreement_factory,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_send_error,
    mock_get_accepted_transfer_for_account,
):
    mock_agreement = agreement_factory(pma_account_id="")
    mock_get_agreements_by_query.return_value = [mock_agreement]

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_send_error.call_count == 1
    mock_send_error.assert_called_once_with(
        "Synchronize AWS agreement subscriptions",
        f"{mock_agreement.get('id')} - Skipping - PMA not found",
    )
    mock_get_accepted_transfer_for_account.assert_not_called()


def test_synchronize_agreements_exception_during_awsclient_instantiation(
    mocker,
    config,
    mock_send_exception,
    mock_awsclient,
    mock_get_agreements_by_query,
    mpt_client,
    fulfillment_parameters_factory,
    agreement,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.get_accepted_transfer_for_account",
        side_effect=Exception("Failed to assume role"),
    )

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_send_exception.call_count == 1
    mock_send_exception.assert_called_once_with(
        "Fetching responsibility transfers",
        "AGR-2119-4550-8674-5962 - Error occurred while fetching responsibility transfers",
    )


def test_synchronize_agreements_with_no_active_transfer(
    mpt_client,
    config,
    agreement_factory,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_get_accepted_transfer_for_account,
    mock_send_warning,
    mock_terminate_agreement,
):
    mock_agreement = agreement_factory()
    mock_get_agreements_by_query.return_value = [mock_agreement]
    mock_get_accepted_transfer_for_account.return_value = None

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_send_warning.call_count == 1
    mock_send_warning.assert_called_once_with(
        "Synchronize AWS agreement subscriptions",
        "AGR-2119-4550-8674-5962 - agreement with an inactive transfer - terminating",
    )
    mock_terminate_agreement.assert_called_once_with(mpt_client, mock_agreement, dry_run=False)
    mock_get_accepted_transfer_for_account.assert_called_once_with("651706759263", "225989344502")


def test_synchronize_agreements_with_active_transfer(
    mpt_client,
    config,
    agreement,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_get_accepted_transfer_for_account,
    mock_terminate_agreement,
    mock_sync_responsibility_transfer_id,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_accepted_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_get_accepted_transfer_for_account.call_count == 1
    mock_terminate_agreement.assert_not_called()
    mock_get_accepted_transfer_for_account.assert_called_once_with("651706759263", "225989344502")
    mock_sync_responsibility_transfer_id.assert_called_once_with(
        mpt_client, agreement, "rt-8lr3q6sn", dry_run=False
    )


def test_synchronize_agreements_exception_during_sync(
    mpt_client,
    config,
    agreement,
    mock_get_agreements_by_query,
    mock_awsclient,
    mock_get_accepted_transfer_for_account,
    mock_send_exception,
    mock_sync_responsibility_transfer_id,
    mock_terminate_agreement,
    mock_send_warning,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_accepted_transfer_for_account.return_value = None
    error_msg = "Test sync error"
    mock_terminate_agreement.side_effect = Exception(error_msg)

    with pytest.raises(Exception, match=error_msg):
        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)

    assert mock_get_accepted_transfer_for_account.call_count == 1
    mock_get_accepted_transfer_for_account.assert_called_once_with("651706759263", "225989344502")
    mock_sync_responsibility_transfer_id.assert_not_called()


def test_get_accepted_inbound_responsibility_transfers_success(
    config, mock_awsclient, responsibility_transfer_factory
):
    pma_account_id = "123456789012"
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
    ]
    mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

    result = get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert result == {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        },
    }
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_inbound_responsibility_transfers_empty(
    config, mock_awsclient, responsibility_transfer_factory
):
    pma_account_id = "123456789012"
    mock_awsclient.get_inbound_responsibility_transfers.return_value = []

    result = get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert result == {}
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_inbound_responsibility_transfers_error(config, mock_awsclient):
    pma_account_id = "123456789012"
    mock_awsclient.get_inbound_responsibility_transfers.side_effect = Exception("Error occurred")

    with pytest.raises(Exception, match="Error occurred"):
        get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_inbound_responsibility_transfers_all_inactive(
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
            source="source4", status=ResponsibilityTransferStatus.WITHDRAWN.value
        ),
    ]
    mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

    result = get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert result == {}
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_inbound_responsibility_transfers_skips_without_source(
    config, mock_awsclient, responsibility_transfer_factory
):
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

    result = get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert result == {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        },
    }


def test_get_accepted_transfer_for_account_returns_transfer_when_found(
    mocker, config, mock_awsclient
):
    mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.get_accepted_inbound_responsibility_transfers",
        return_value={
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "Status": ResponsibilityTransferStatus.ACCEPTED.value,
            },
        },
    )

    result = get_accepted_transfer_for_account("651706759263", "225989344502")

    assert result == {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }


def test_get_accepted_transfer_for_account_returns_none_when_not_found(
    mocker, config, mock_awsclient
):
    mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.get_accepted_inbound_responsibility_transfers",
        return_value={
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "Status": ResponsibilityTransferStatus.ACCEPTED.value,
            },
        },
    )

    result = get_accepted_transfer_for_account("651706759263", "999999999999")

    assert result is None


def test_terminate_agreement_terminates_active_subscriptions(
    mpt_client, agreement_factory, mock_terminate_subscription
):
    terminate_agreement(mpt_client, agreement_factory(), dry_run=False)  # act

    assert mock_terminate_subscription.call_count == 1
    mock_terminate_subscription.assert_called_once_with(
        mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
    )


def test_terminate_agreement_logs_error_for_failures(
    mpt_client, agreement_factory, mock_terminate_subscription, mock_send_exception
):
    mock_terminate_subscription.side_effect = Exception("Mocked error")

    terminate_agreement(mpt_client, agreement_factory(), dry_run=False)  # act

    assert mock_terminate_subscription.call_count == 1
    mock_terminate_subscription.assert_called_once_with(
        mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
    )
    assert mock_send_exception.call_count == 1
    mock_send_exception.assert_called_once_with(
        "Inactive transfer",
        "AGR-2119-4550-8674-5962 - terminating agreement due to inactive transfer - "
        "error terminating subscription SUB-1000-2000-3000.",
    )


def test_terminate_agreement_dry_run_skips_termination(
    mpt_client, agreement_factory, mock_terminate_subscription
):
    terminate_agreement(mpt_client, agreement_factory(), dry_run=True)  # act

    mock_terminate_subscription.assert_not_called()


def test_sync_responsibility_transfer_id_no_change(
    mpt_client, mock_send_exception, agreement_factory, mock_update_agreement
):
    agreement = agreement_factory()
    responsibility_transfer_id = agreement["parameters"]["fulfillment"][1]["value"]

    sync_responsibility_transfer_id(
        mpt_client, agreement, responsibility_transfer_id, dry_run=False
    )  # act

    mock_update_agreement.assert_not_called()
    mock_send_exception.assert_not_called()


def test_sync_responsibility_transfer_id_update(
    mpt_client, mock_send_exception, agreement_factory, mock_update_agreement
):
    agreement = agreement_factory()
    pma_account_id = "PMA-123456"

    sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=False)  # act

    assert mock_update_agreement.call_count == 1
    mock_update_agreement.assert_called_once_with(
        mpt_client,
        "AGR-2119-4550-8674-5962",
        parameters={
            "fulfillment": [{"externalId": "responsibilityTransferId", "value": "PMA-123456"}]
        },
    )
    mock_send_exception.assert_not_called()


def test_sync_responsibility_transfer_id_dry_run(
    mpt_client, caplog, agreement_factory, mock_update_agreement
):
    agreement = agreement_factory()
    pma_account_id = "PMA-123456"

    sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=True)  # act

    assert caplog.messages == [
        "AGR-2119-4550-8674-5962 - synchronizing responsibility transfer ID: PMA-123456",
        (
            "AGR-2119-4550-8674-5962 - dry run mode - skipping update with parameters: "
            "{'fulfillment': [{'externalId': 'responsibilityTransferId', 'value': "
            "'PMA-123456'}]}"
        ),
    ]
    mock_update_agreement.assert_not_called()


def test_sync_responsibility_transfer_id_exception(
    mpt_client, mock_send_exception, agreement_factory, mock_update_agreement
):
    agreement = agreement_factory()
    pma_account_id = "PMA-123456"
    mock_update_agreement.side_effect = Exception("Update Error")

    sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=False)  # act

    assert mock_send_exception.call_count == 1
    mock_send_exception.assert_called_once_with(
        "Synchronize PMA account id",
        "AGR-2119-4550-8674-5962 - failed to update agreement with responsibility "
        "transfer ID PMA-123456",
    )
