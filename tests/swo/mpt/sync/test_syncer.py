import datetime as dt

import pytest

from swo_aws_extension.constants import (
    ResponsibilityTransferStatus,
)
from swo_aws_extension.swo.mpt.sync.syncer import (
    get_latest_inbound_responsibility_transfers,
    sync_responsibility_transfer_id,
    synchronize_agreements,
    terminate_agreement,
)


@pytest.fixture(autouse=True)
def clear_function_cache():
    """Clear cache for cached functions between tests."""
    yield
    get_latest_inbound_responsibility_transfers.cache_clear()


class TestSynchronizeAgreements:
    def test_with_specific_ids(
        self,
        mpt_client,
        config,
        agreement,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_get_latest_inbound_responsibility_transfers,
        mock_sync_responsibility_transfer_id,
    ):
        mock_get_agreements_by_query.return_value = [agreement]
        mock_get_latest_inbound_responsibility_transfers.return_value = {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.ACCEPTED,
            }
        }

        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

        mock_get_latest_inbound_responsibility_transfers.assert_called_once_with("651706759263")
        mock_sync_responsibility_transfer_id.assert_called_once_with(
            mpt_client, agreement, "rt-8lr3q6sn", dry_run=False
        )

    def test_without_ids(
        self,
        mpt_client,
        config,
        agreement,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_get_latest_inbound_responsibility_transfers,
        mock_sync_responsibility_transfer_id,
    ):
        mock_get_agreements_by_query.return_value = [agreement]
        mock_get_latest_inbound_responsibility_transfers.return_value = {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.ACCEPTED,
            }
        }

        synchronize_agreements(mpt_client, [], ["PROD-123-456"], dry_run=False)  # act

        mock_get_latest_inbound_responsibility_transfers.assert_called_once_with("651706759263")
        mock_sync_responsibility_transfer_id.assert_called_once_with(
            mpt_client, agreement, "rt-8lr3q6sn", dry_run=False
        )

    def test_missing_mpa_account(
        self,
        mpt_client,
        config,
        agreement_factory,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_send_error,
        mock_get_latest_inbound_responsibility_transfers,
    ):
        mock_agreement = agreement_factory(vendor_id="")
        mock_get_agreements_by_query.return_value = [mock_agreement]

        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

        mock_send_error.assert_called_once_with(
            "Synchronize AWS agreement subscriptions",
            f"{mock_agreement.get('id')} - Skipping - MPA not found",
        )
        mock_get_latest_inbound_responsibility_transfers.assert_not_called()

    def test_missing_pma_account(
        self,
        mpt_client,
        config,
        agreement_factory,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_send_error,
        mock_get_latest_inbound_responsibility_transfers,
    ):
        mock_agreement = agreement_factory(pma_account_id="")
        mock_get_agreements_by_query.return_value = [mock_agreement]

        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

        mock_send_error.assert_called_once_with(
            "Synchronize AWS agreement subscriptions",
            f"{mock_agreement.get('id')} - Skipping - PMA not found",
        )
        mock_get_latest_inbound_responsibility_transfers.assert_not_called()

    def test_exception_during_awsclient_instantiation(
        self,
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
            "swo_aws_extension.swo.mpt.sync.syncer.AWSClient",
            side_effect=Exception("Failed to assume role"),
        )

        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

        mock_send_exception.assert_called_once_with(
            "Fetching responsibility transfers",
            "AGR-2119-4550-8674-5962 - Error occurred while fetching responsibility transfers",
        )

    def test_with_inactive_transfer(
        self,
        mpt_client,
        config,
        agreement_factory,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_get_latest_inbound_responsibility_transfers,
        mock_send_warning,
        mock_terminate_agreement,
        responsibility_transfer_factory,
    ):
        mock_agreement = agreement_factory()
        mock_get_agreements_by_query.return_value = [mock_agreement]
        mock_get_latest_inbound_responsibility_transfers.return_value = {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.DECLINED,
            }
        }

        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

        mock_send_warning.assert_called_once_with(
            "Synchronize AWS agreement subscriptions",
            "AGR-2119-4550-8674-5962 - agreement with an inactive transfer - terminating "
            "- {'Id': 'rt-8lr3q6sn', 'StartTimestamp': datetime.datetime(2025, 11, 1, 0, "
            "0, tzinfo=datetime.timezone.utc), 'Status': "
            "<ResponsibilityTransferStatus.DECLINED: 'DECLINED'>}",
        )
        mock_terminate_agreement.assert_called_once_with(mpt_client, mock_agreement, dry_run=False)
        mock_get_latest_inbound_responsibility_transfers.assert_called_once_with("651706759263")

    def test_synchronize_agreements_with_active_transfer(
        self,
        mpt_client,
        config,
        agreement,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_get_latest_inbound_responsibility_transfers,
        mock_terminate_agreement,
        mock_sync_responsibility_transfer_id,
    ):
        mock_get_agreements_by_query.return_value = [agreement]
        mock_get_latest_inbound_responsibility_transfers.return_value = {
            "225989344502": {"Id": "rt-8lr3q6sn", "Status": "ACCEPTED"}
        }

        synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

        mock_terminate_agreement.assert_not_called()
        mock_get_latest_inbound_responsibility_transfers.assert_called_once_with("651706759263")
        mock_sync_responsibility_transfer_id.assert_called_once_with(
            mpt_client, agreement, "rt-8lr3q6sn", dry_run=False
        )

    def test_synchronize_agreements_exception_during_sync(
        self,
        mpt_client,
        config,
        agreement,
        mock_get_agreements_by_query,
        mock_awsclient,
        mock_get_latest_inbound_responsibility_transfers,
        mock_send_exception,
        mock_sync_responsibility_transfer_id,
        mock_terminate_agreement,
        mock_send_warning,
    ):
        mock_get_agreements_by_query.return_value = [agreement]
        mock_get_latest_inbound_responsibility_transfers.return_value = {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.DECLINED,
            }
        }
        error_msg = "Test sync error"
        mock_terminate_agreement.side_effect = Exception(error_msg)

        with pytest.raises(Exception, match=error_msg):
            synchronize_agreements(
                mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False
            )  # act

        mock_get_latest_inbound_responsibility_transfers.assert_called_once_with("651706759263")
        mock_sync_responsibility_transfer_id.assert_not_called()


class TestGetActiveInboundResponsibilityTransfers:
    def test_success(self, mocker, config, mock_awsclient, responsibility_transfer_factory):
        mpa_account_id = "123456789012"
        transfers = [
            responsibility_transfer_factory(
                source="225989344502", status=ResponsibilityTransferStatus.ACCEPTED
            ),
            responsibility_transfer_factory(
                source="651706759263", status=ResponsibilityTransferStatus.REQUESTED
            ),
            responsibility_transfer_factory(
                source="651706759264", status=ResponsibilityTransferStatus.DECLINED
            ),
        ]
        mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

        result = get_latest_inbound_responsibility_transfers(mpa_account_id)

        assert result == {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.ACCEPTED,
            },
            "651706759263": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.REQUESTED,
            },
            "651706759264": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.DECLINED,
            },
        }
        mock_awsclient.get_inbound_responsibility_transfers.assert_called_once_with()

    def test_empty_inbound_transfers(
        self, mocker, config, mock_awsclient, responsibility_transfer_factory
    ):
        mpa_account_id = "123456789012"
        mock_awsclient.get_inbound_responsibility_transfers.return_value = []

        result = get_latest_inbound_responsibility_transfers(mpa_account_id)

        assert result == {}
        mock_awsclient.get_inbound_responsibility_transfers.assert_called_once_with()

    def test_error_while_fetching_transfers(self, mocker, config, mock_awsclient):
        mpa_account_id = "123456789012"
        mock_awsclient.get_inbound_responsibility_transfers.side_effect = Exception(
            "Error occurred"
        )

        with pytest.raises(Exception, match="Error occurred"):
            get_latest_inbound_responsibility_transfers(mpa_account_id)

        mock_awsclient.get_inbound_responsibility_transfers.assert_called_once()

    def test_same_source_keeps_most_recent(
        self, mocker, config, mock_awsclient, responsibility_transfer_factory
    ):
        mpa_account_id = "123456789012"
        transfer_older = responsibility_transfer_factory(
            status=ResponsibilityTransferStatus.ACCEPTED, start_timestamp="2025-11-01T00:00:00Z"
        )
        transfer_newer = responsibility_transfer_factory(
            status=ResponsibilityTransferStatus.REQUESTED, start_timestamp="2025-10-01T00:00:00Z"
        )
        mock_awsclient.get_inbound_responsibility_transfers.return_value = [
            transfer_older,
            transfer_newer,
        ]

        result = get_latest_inbound_responsibility_transfers(mpa_account_id)

        assert result == {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.ACCEPTED,
            }
        }
        mock_awsclient.get_inbound_responsibility_transfers.assert_called_once()

    def test_all_inactive_statuses_filtered_out(
        self, mocker, config, mock_awsclient, responsibility_transfer_factory
    ):
        mpa_account_id = "123456789012"
        transfers = [
            responsibility_transfer_factory(status=ResponsibilityTransferStatus.DECLINED),
            responsibility_transfer_factory(status=ResponsibilityTransferStatus.CANCELED),
            responsibility_transfer_factory(status=ResponsibilityTransferStatus.EXPIRED),
            responsibility_transfer_factory(status=ResponsibilityTransferStatus.WITHDRAWN),
        ]
        mock_awsclient.get_inbound_responsibility_transfers.return_value = transfers

        result = get_latest_inbound_responsibility_transfers(mpa_account_id)

        assert result == {
            "225989344502": {
                "Id": "rt-8lr3q6sn",
                "StartTimestamp": dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
                "Status": ResponsibilityTransferStatus.DECLINED,
            }
        }
        mock_awsclient.get_inbound_responsibility_transfers.assert_called_once()


class TestTerminateAgreement:
    def test_terminates_active_subscriptions(
        self, mpt_client, agreement_factory, mock_terminate_subscription
    ):
        terminate_agreement(mpt_client, agreement_factory(), dry_run=False)  # act

        mock_terminate_subscription.assert_any_call(
            mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
        )
        mock_terminate_subscription.assert_called_once_with(
            mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
        )

    def test_logs_error_for_failures(
        self, mpt_client, agreement_factory, mock_terminate_subscription, mock_send_exception
    ):
        mock_terminate_subscription.side_effect = Exception("Mocked error")

        terminate_agreement(mpt_client, agreement_factory(), dry_run=False)  # act

        mock_terminate_subscription.assert_called_once_with(
            mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
        )
        mock_send_exception.assert_called_once_with(
            "Inactive transfer",
            "AGR-2119-4550-8674-5962 - terminating agreement due to inactive transfer - "
            "error terminating subscription SUB-1000-2000-3000.",
        )

    def test_dry_run_skips_termination(
        self, mpt_client, agreement_factory, mock_terminate_subscription
    ):
        terminate_agreement(mpt_client, agreement_factory(), dry_run=True)  # act

        mock_terminate_subscription.assert_not_called()


class TestSyncPmaAccountId:
    def test_no_change(
        self, mpt_client, mock_send_exception, agreement_factory, mock_update_agreement
    ):
        agreement = agreement_factory()
        pma_account_id = agreement["parameters"]["fulfillment"][0]["value"]

        sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=False)  # act

        mock_update_agreement.assert_not_called()
        mock_send_exception.assert_not_called()

    def test_update(
        self, mpt_client, mock_send_exception, agreement_factory, mock_update_agreement
    ):
        agreement = agreement_factory()
        pma_account_id = "PMA-123456"

        sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=False)  # act

        mock_update_agreement.assert_called_once_with(
            mpt_client,
            "AGR-2119-4550-8674-5962",
            parameters={
                "fulfillment": [{"externalId": "responsibilityTransferId", "value": "PMA-123456"}]
            },
        )
        mock_send_exception.assert_not_called()

    def test_dry_run(self, mpt_client, caplog, agreement_factory, mock_update_agreement):
        agreement = agreement_factory()
        pma_account_id = "PMA-123456"

        sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=True)  # act

        assert caplog.messages == [
            "AGR-2119-4550-8674-5962 - synchronizing responsibility transfer ID: PMA-123456",
            "AGR-2119-4550-8674-5962 - dry run mode - skipping update with parameters: "
            "{'fulfillment': [{'externalId': 'responsibilityTransferId', 'value': "
            "'PMA-123456'}]}",
        ]
        mock_update_agreement.assert_not_called()

    def test_exception(
        self, mpt_client, mock_send_exception, agreement_factory, mock_update_agreement
    ):
        agreement = agreement_factory()
        pma_account_id = "PMA-123456"
        mock_update_agreement.side_effect = Exception("Update Error")

        sync_responsibility_transfer_id(mpt_client, agreement, pma_account_id, dry_run=False)  # act

        mock_send_exception.assert_called_once_with(
            "Synchronize PMA account id",
            "AGR-2119-4550-8674-5962 - failed to update agreement with responsibility "
            "transfer ID PMA-123456",
        )
