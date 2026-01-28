import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    ResponsibilityTransferStatus,
)
from swo_aws_extension.swo.mpt.sync.syncer import (
    AgreementProcessorError,
    get_accepted_inbound_responsibility_transfers,
    get_accepted_transfer_for_account,
    synchronize_agreements,
)


@pytest.fixture(autouse=True)
def clear_function_cache():
    """Clear cache for cached functions between tests."""
    yield
    get_accepted_inbound_responsibility_transfers.cache_clear()


def test_agreement_syncer_sync_success(
    agreement,
    mock_get_accepted_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    syncer,
):
    mock_get_accepted_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    syncer.process(agreement)  # act

    mock_get_accepted_transfer_for_account.assert_called_once_with("651706759263", "225989344502")
    mock_sync_responsibility_transfer_id_method.assert_called_once_with(
        syncer.mpt_client, agreement, "rt-8lr3q6sn"
    )


@pytest.mark.parametrize(
    ("factory_kwargs", "expected_msg", "expected_op"),
    [
        (
            {"vendor_id": ""},
            "Skipping - MPA not found",
            "Synchronize AWS agreement subscriptions",
        ),
        (
            {"pma_account_id": ""},
            "Skipping - PMA not found",
            "Synchronize AWS agreement subscriptions",
        ),
    ],
)
def test_agreement_syncer_sync_missing_accounts(
    agreement_factory,
    mock_send_warning,
    syncer,
    factory_kwargs,
    expected_msg,
    expected_op,
):
    mock_agreement = agreement_factory(**factory_kwargs)

    syncer.process(mock_agreement)  # act

    mock_send_warning.assert_called_once_with(
        expected_op, f"{mock_agreement.get('id')} - {expected_msg}"
    )


def test_agreement_syncer_sync_aws_exception(
    agreement,
    mock_send_warning,
    mock_get_accepted_transfer_for_account,
    syncer,
):
    mock_get_accepted_transfer_for_account.side_effect = Exception("error")

    syncer.process(agreement)  # act

    mock_send_warning.assert_called_once_with(
        "Synchronize AWS agreement subscriptions",
        f"{agreement.get('id')} - Error occurred while fetching responsibility transfers",
    )


def test_agreement_syncer_sync_no_active_transfer(
    agreement_factory,
    mock_get_accepted_transfer_method,
    mock_send_warning,
    mock_terminate_agreement_method,
    mock_delete_billing_group_method,
    mock_remove_apn_method,
    syncer,
):
    mock_agreement = agreement_factory()
    mock_get_accepted_transfer_method.return_value = None

    syncer.process(mock_agreement)  # act

    mock_send_warning.assert_called_once_with(
        "Synchronize AWS agreement subscriptions",
        f"{mock_agreement.get('id')} - agreement with an inactive transfer - terminating",
    )
    mock_terminate_agreement_method.assert_called_once_with(mock_agreement)
    mock_delete_billing_group_method.assert_called_once_with(mock_agreement, "651706759263")
    mock_remove_apn_method.assert_called_once_with(mock_agreement, "651706759263")


def test_sync_agreements_with_active_transfer(
    agreement,
    mock_get_agreements_by_query,
    mock_get_accepted_transfer_method,
    mock_terminate_agreement_method,
    mock_delete_billing_group_method,
    mock_sync_responsibility_transfer_id_method,
    mpt_client,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_accepted_transfer_method.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_get_accepted_transfer_method.call_count == 1
    mock_terminate_agreement_method.assert_not_called()
    mock_delete_billing_group_method.assert_not_called()
    mock_get_accepted_transfer_method.assert_called_once_with(
        agreement, "225989344502", "651706759263"
    )
    mock_sync_responsibility_transfer_id_method.assert_called_once_with(
        mpt_client, agreement, "rt-8lr3q6sn"
    )


def test_synchronize_agreements_exception(
    agreement,
    mock_get_accepted_transfer_method,
    mock_terminate_agreement_method,
    syncer,
    mock_send_exception,
):
    mock_get_accepted_transfer_method.return_value = None
    error_msg = "Test sync error"
    mock_terminate_agreement_method.side_effect = Exception(error_msg)

    syncer.process(agreement)  # act

    assert mock_get_accepted_transfer_method.call_count == 1
    mock_get_accepted_transfer_method.assert_called_once_with(
        agreement, "225989344502", "651706759263"
    )
    mock_send_exception.assert_called_once()


def test_get_accepted_transfers_success(config, mock_awsclient, responsibility_transfer_factory):
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

    result = get_accepted_inbound_responsibility_transfers(pma_account_id)  # act

    assert result == {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        },
    }
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_transfers_empty(config, mock_awsclient, responsibility_transfer_factory):
    pma_account_id = "123456789012"
    mock_awsclient.get_inbound_responsibility_transfers.return_value = []

    result = get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert result == {}
    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_transfers_error(config, mock_awsclient):
    pma_account_id = "123456789012"
    mock_awsclient.get_inbound_responsibility_transfers.side_effect = Exception("Error occurred")

    with pytest.raises(Exception, match="Error occurred"):
        get_accepted_inbound_responsibility_transfers(pma_account_id)

    assert mock_awsclient.get_inbound_responsibility_transfers.call_count == 1


def test_get_accepted_transfers_all_inactive(
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


def test_get_accepted_transfers_no_source(config, mock_awsclient, responsibility_transfer_factory):
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


def test_get_transfer_for_account_found(
    mock_get_responsibility_transfers,
):
    mock_get_responsibility_transfers.return_value = {
        "225989344502": {
            "Id": "rt-8lr3q6sn",
            "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        },
    }

    result = get_accepted_transfer_for_account("651706759263", "225989344502")

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

    result = get_accepted_transfer_for_account("651706759263", "999999999999")

    assert result is None


def test_terminate_agr(agreement_factory, mock_terminate_subscription, syncer):
    syncer.terminate_agreement(agreement_factory())  # act

    assert mock_terminate_subscription.call_count == 1
    mock_terminate_subscription.assert_called_once_with(
        syncer.mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
    )


def test_terminate_agr_logs_error(
    agreement_factory, mock_terminate_subscription, mock_send_exception, syncer
):
    mock_terminate_subscription.side_effect = Exception("Mocked error")

    syncer.terminate_agreement(agreement_factory())  # act

    assert mock_terminate_subscription.call_count == 1
    mock_terminate_subscription.assert_called_once_with(
        syncer.mpt_client, "SUB-1000-2000-3000", "Suspected Lost Customer"
    )
    assert mock_send_exception.call_count == 1
    mock_send_exception.assert_called_once_with(
        "Inactive transfer",
        "AGR-2119-4550-8674-5962 - terminating agreement due to inactive transfer - "
        "error terminating subscription SUB-1000-2000-3000.",
    )


def test_terminate_agr_dry_run(agreement_factory, mock_terminate_subscription, syncer_dry_run):
    syncer_dry_run.terminate_agreement(agreement_factory())  # act

    mock_terminate_subscription.assert_not_called()


def test_sync_transfer_id_no_change(
    mock_send_exception, agreement_factory, mock_update_agreement, syncer
):
    agreement = agreement_factory()
    responsibility_transfer_id = agreement["parameters"]["fulfillment"][1]["value"]

    syncer.sync_responsibility_transfer_id(
        syncer.mpt_client, agreement, responsibility_transfer_id
    )  # act

    mock_update_agreement.assert_not_called()
    mock_send_exception.assert_not_called()


def test_sync_transfer_id_update(
    mock_send_exception, agreement_factory, mock_update_agreement, syncer
):
    agreement = agreement_factory()
    pma_account_id = "PMA-123456"

    syncer.sync_responsibility_transfer_id(syncer.mpt_client, agreement, pma_account_id)  # act

    assert mock_update_agreement.call_count == 1
    mock_update_agreement.assert_called_once_with(
        syncer.mpt_client,
        "AGR-2119-4550-8674-5962",
        parameters={
            "fulfillment": [{"externalId": "responsibilityTransferId", "value": "PMA-123456"}]
        },
    )
    mock_send_exception.assert_not_called()


def test_sync_transfer_id_dry_run(agreement_factory, mock_update_agreement, syncer_dry_run):
    agreement = agreement_factory()
    pma_account_id = "PMA-123456"

    syncer_dry_run.sync_responsibility_transfer_id(
        syncer_dry_run.mpt_client, agreement, pma_account_id
    )  # act

    mock_update_agreement.assert_not_called()


def test_delete_billing_group_success(
    agreement, mock_awsclient, mock_get_billing_group_arn, syncer
):
    mock_get_billing_group_arn.return_value = (
        "arn:aws:billingconductor::123456789012:billinggroup/bg-1"
    )

    syncer.delete_billing_group(agreement, "123456789")  # act

    mock_awsclient.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123456789012:billinggroup/bg-1"
    )


def test_delete_billing_group_no_arn(agreement, mock_awsclient, mock_get_billing_group_arn, syncer):
    mock_get_billing_group_arn.return_value = ""

    syncer.delete_billing_group(agreement, "123456789")  # act

    mock_awsclient.delete_billing_group.assert_not_called()


def test_delete_billing_group_dry_run(
    agreement, mock_awsclient, mock_get_billing_group_arn, syncer_dry_run
):
    arn = "arn:aws:billingconductor::123456789012:billinggroup/bg-1"
    mock_get_billing_group_arn.return_value = arn

    syncer_dry_run.delete_billing_group(agreement, "123456789")  # act

    mock_awsclient.delete_billing_group.assert_not_called()


def test_delete_billing_group_aws_error(
    agreement, mock_awsclient, mock_get_billing_group_arn, syncer
):
    arn = "arn:aws:billingconductor::123456789012:billinggroup/bg-1"
    mock_get_billing_group_arn.return_value = arn
    mock_awsclient.delete_billing_group.side_effect = AWSError("error")

    syncer.delete_billing_group(agreement, "123456789")  # act

    mock_awsclient.delete_billing_group.assert_called_once_with(arn)


def test_remove_apn_success(agreement, mock_awsclient, mock_get_relationship_id, syncer):
    mock_get_relationship_id.return_value = "rel-123"
    mock_awsclient.get_program_management_id_by_account.return_value = "pm-123"

    syncer.remove_apn(agreement, "123456789012")  # act

    mock_awsclient.get_program_management_id_by_account.assert_called_once_with("123456789012")
    mock_awsclient.delete_pc_relationship.assert_called_once_with("pm-123", "rel-123")


def test_remove_apn_no_relationship_id(agreement, mock_awsclient, mock_get_relationship_id, syncer):
    mock_get_relationship_id.return_value = None

    syncer.remove_apn(agreement, "123456789012")  # act

    mock_awsclient.get_program_management_id_by_account.assert_not_called()


def test_remove_apn_pm_id_not_found(agreement, mock_awsclient, mock_get_relationship_id, syncer):
    mock_get_relationship_id.return_value = "rel-123"
    mock_awsclient.get_program_management_id_by_account.side_effect = AWSError("not found")

    syncer.remove_apn(agreement, "123456789012")  # act

    mock_awsclient.delete_pc_relationship.assert_not_called()


def test_remove_apn_delete_error(agreement, mock_awsclient, mock_get_relationship_id, syncer):
    mock_get_relationship_id.return_value = "rel-123"
    mock_awsclient.get_program_management_id_by_account.return_value = "pm-123"
    mock_awsclient.delete_pc_relationship.side_effect = AWSError("error")

    syncer.remove_apn(agreement, "123456789012")  # act

    mock_awsclient.delete_pc_relationship.assert_called_once()


def test_remove_apn_dry_run(agreement, mock_awsclient, mock_get_relationship_id, syncer_dry_run):
    mock_get_relationship_id.return_value = "rel-123"
    mock_awsclient.get_program_management_id_by_account.return_value = "pm-123"

    syncer_dry_run.remove_apn(agreement, "123456789012")  # act

    mock_awsclient.get_program_management_id_by_account.assert_called_once_with("123456789012")
    mock_awsclient.delete_pc_relationship.assert_not_called()


def test_agreement_error(agreement, mock_get_mpa_method, mock_send_warning, syncer):
    mock_get_mpa_method.side_effect = AgreementProcessorError("error", "op")

    syncer.process(agreement)  # act

    mock_send_warning.assert_called_once_with("op", "error")


def test_sync_responsibility_transfer_id_error(
    agreement,
    mock_send_exception,
    syncer,
    mock_update_agreement,
    mock_get_responsibility_transfer_id,
):
    mock_update_agreement.side_effect = Exception("error")
    mock_get_responsibility_transfer_id.return_value = "old"

    syncer.sync_responsibility_transfer_id(syncer.mpt_client, agreement, "new")  # act

    mock_send_exception.assert_called_once()


def test_get_mpa(agreement, syncer):
    result = syncer.get_mpa(agreement)

    assert result == "225989344502"


def test_get_pma(agreement, syncer):
    result = syncer.get_pma(agreement)

    assert result == "651706759263"
