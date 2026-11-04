import datetime as dt

import pytest
from freezegun import freeze_time
from mpt_api_client.exceptions import MPTError

from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.swo.crm_service.errors import CRMError
from swo_aws_extension.swo.mpt.sync.agreement_syncer import (
    AgreementProcessorError,
    synchronize_agreements,
)


def test_agreement_syncer_sync_success(
    agreement,
    mock_get_available_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    syncer,
):
    mock_get_available_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    syncer.process(agreement)  # act

    mock_get_available_transfer_for_account.assert_called_once_with("651706759263", "225989344502")
    mock_sync_responsibility_transfer_id_method.assert_called_once_with(agreement, "rt-8lr3q6sn")


@pytest.mark.parametrize(
    ("factory_kwargs", "expected_msg"),
    [
        ({"vendor_id": ""}, "Skipping - MPA not found"),
        ({"pma_account_id": ""}, "Skipping - PMA not found"),
    ],
)
def test_agreement_syncer_sync_missing_accounts(
    agreement_factory,
    mock_send_warning,
    syncer,
    factory_kwargs,
    expected_msg,
):
    mock_agreement = agreement_factory(**factory_kwargs)

    syncer.process(mock_agreement)  # act

    mock_send_warning.assert_called_once_with(
        f"{mock_agreement.get('id')} - Synchronize AWS agreement", expected_msg
    )


def test_agreement_syncer_sync_aws_exception(
    agreement,
    mock_send_warning,
    mock_get_available_transfer_for_account,
    syncer,
):
    mock_get_available_transfer_for_account.side_effect = Exception("error")

    syncer.process(agreement)  # act

    mock_send_warning.assert_called_once_with(
        f"{agreement.get('id')} - Synchronize AWS agreement",
        "Error occurred while fetching responsibility transfers",
    )


def test_agreement_syncer_sync_no_active_transfer(
    agreement_factory,
    mock_get_available_transfer_method,
    mock_send_warning,
    mock_terminate_agreement_method,
    syncer,
):
    mock_agreement = agreement_factory()
    mock_get_available_transfer_method.return_value = None

    syncer.process(mock_agreement)  # act

    mock_send_warning.assert_called_once_with(
        f"{mock_agreement.get('id')} - Synchronize AWS agreement subscriptions",
        "Agreement with an inactive transfer - terminating",
    )
    mock_terminate_agreement_method.assert_called_once_with(mock_agreement)


@freeze_time("2026-08-06")
def test_agreement_syncer_notifies_scheduled_transfer_end(
    mocker,
    agreement,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_available_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    mock_get_crm_terminate_order_ticket_id,
    mock_crm_service_client,
    mock_update_agreement,
    mock_terminate_agreement_method,
    syncer,
):
    end_date = dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00")
    mock_get_available_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        "EndTimestamp": end_date,
    }
    mock_get_crm_terminate_order_ticket_id.return_value = ""
    mock_crm_service_client.create_service_request.return_value = {"id": "TICKET-123"}

    syncer.process(agreement)  # act

    service_request = mock_crm_service_client.create_service_request.call_args.args[1]
    expected_end_date = end_date.strftime("%Y-%m-%d %H:%M:%S")
    assert f"Termination date: <b>{expected_end_date}</b>" in service_request.summary
    assert mock_update_agreement.call_args_list == [
        mocker.call(
            syncer.mpt_client,
            agreement["id"],
            parameters={
                "fulfillment": [
                    {"externalId": "relationshipEndDate", "value": end_date.isoformat()}
                ]
            },
        ),
        mocker.call(
            syncer.mpt_client,
            agreement["id"],
            parameters={
                "fulfillment": [{"externalId": "crmTerminateOrderTicketId", "value": "TICKET-123"}]
            },
        ),
    ]
    mock_terminate_agreement_method.assert_not_called()
    mock_sync_responsibility_transfer_id_method.assert_called_once_with(agreement, "rt-8lr3q6sn")


@freeze_time("2026-08-06")
def test_agreement_syncer_notifies_transfer_end_only_once(
    agreement,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_available_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    mock_get_crm_terminate_order_ticket_id,
    mock_crm_service_client,
    mock_update_agreement,
    syncer,
):
    mock_get_available_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        "EndTimestamp": dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00"),
    }
    mock_get_crm_terminate_order_ticket_id.return_value = "TICKET-123"

    syncer.process(agreement)  # act

    mock_crm_service_client.create_service_request.assert_not_called()
    assert mock_update_agreement.call_count == 1
    updated_parameters = mock_update_agreement.call_args.kwargs["parameters"]
    assert updated_parameters["fulfillment"][0]["externalId"] == "relationshipEndDate"
    mock_sync_responsibility_transfer_id_method.assert_called_once_with(agreement, "rt-8lr3q6sn")


@freeze_time("2026-08-06")
def test_agreement_syncer_notify_transfer_end_dry_run(
    agreement,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_available_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    mock_get_crm_terminate_order_ticket_id,
    mock_crm_service_client,
    mock_update_agreement,
    syncer_dry_run,
):
    mock_get_available_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        "EndTimestamp": dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00"),
    }
    mock_get_crm_terminate_order_ticket_id.return_value = ""

    syncer_dry_run.process(agreement)  # act

    mock_crm_service_client.create_service_request.assert_not_called()
    mock_update_agreement.assert_not_called()


@freeze_time("2026-08-06")
def test_agreement_syncer_notify_transfer_end_crm_error(
    agreement,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_available_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    mock_get_crm_terminate_order_ticket_id,
    mock_crm_service_client,
    mock_update_agreement,
    mock_send_exception,
    syncer,
):
    mock_get_available_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        "EndTimestamp": dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00"),
    }
    mock_get_crm_terminate_order_ticket_id.return_value = ""
    mock_crm_service_client.create_service_request.side_effect = CRMError("error")

    syncer.process(agreement)  # act

    assert mock_update_agreement.call_count == 1  # only the relationship end date sync
    mock_send_exception.assert_called_once_with(
        f"{agreement['id']} - Transfer end notification",
        "Failed to create the transfer end termination ticket",
    )


@freeze_time("2026-08-06")
def test_agreement_syncer_notify_transfer_end_update_agreement_error(
    agreement,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mock_get_available_transfer_for_account,
    mock_sync_responsibility_transfer_id_method,
    mock_get_crm_terminate_order_ticket_id,
    mock_crm_service_client,
    mock_update_agreement,
    mock_send_exception,
    syncer,
):
    mock_get_available_transfer_for_account.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
        "EndTimestamp": dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00"),
    }
    mock_get_crm_terminate_order_ticket_id.return_value = ""
    mock_crm_service_client.create_service_request.return_value = {"id": "TICKET-123"}
    mock_update_agreement.side_effect = [None, MPTError("error")]

    syncer.process(agreement)  # act

    mock_send_exception.assert_called_once_with(
        f"{agreement['id']} - Transfer end notification",
        "Failed to update agreement with termination ticket ID TICKET-123",
    )


@freeze_time("2026-08-06")
def test_agreement_syncer_terminates_when_transfer_end_date_reached(
    agreement_factory,
    mock_get_available_transfer_method,
    mock_send_warning,
    mock_terminate_agreement_method,
    mock_crm_service_client,
    mock_update_agreement,
    syncer,
):
    end_date = dt.datetime.fromisoformat("2026-07-31T23:59:59+00:00")
    mock_agreement = agreement_factory()
    mock_get_available_transfer_method.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.WITHDRAWN.value,
        "EndTimestamp": end_date,
    }

    syncer.process(mock_agreement)  # act

    mock_update_agreement.assert_called_once_with(
        syncer.mpt_client,
        mock_agreement["id"],
        parameters={
            "fulfillment": [{"externalId": "relationshipEndDate", "value": end_date.isoformat()}]
        },
    )
    mock_terminate_agreement_method.assert_called_once_with(mock_agreement)
    mock_crm_service_client.create_service_request.assert_not_called()
    mock_send_warning.assert_called_once_with(
        f"{mock_agreement.get('id')} - Synchronize AWS agreement subscriptions",
        "Agreement with an inactive transfer - terminating",
    )


def test_sync_relationship_end_date_skips_if_unchanged(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_update_agreement,
    syncer,
):
    end_date = dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00")
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_end_date=end_date.isoformat(),
        )
    )

    syncer.sync_relationship_end_date(agreement, end_date)  # act

    mock_update_agreement.assert_not_called()


def test_sync_relationship_end_date_dry_run(agreement, mock_update_agreement, syncer_dry_run):
    end_date = dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00")

    syncer_dry_run.sync_relationship_end_date(agreement, end_date)  # act

    mock_update_agreement.assert_not_called()


def test_sync_relationship_end_date_error(
    agreement, mock_update_agreement, mock_send_exception, syncer
):
    end_date = dt.datetime.fromisoformat("2026-09-30T23:59:59+00:00")
    mock_update_agreement.side_effect = MPTError("error")

    syncer.sync_relationship_end_date(agreement, end_date)  # act

    mock_send_exception.assert_called_once_with(
        f"{agreement['id']} - Synchronize relationship end date",
        f"Failed to update agreement with relationship end date {end_date.isoformat()}",
    )


def test_sync_agreements_with_active_transfer(
    agreement,
    mock_get_agreements_by_query,
    mock_get_available_transfer_method,
    mock_terminate_agreement_method,
    mock_sync_responsibility_transfer_id_method,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mpt_client,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_available_transfer_method.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    synchronize_agreements(mpt_client, ["AGR-123-456"], ["PROD-123-456"], dry_run=False)  # act

    assert mock_get_available_transfer_method.call_count == 1
    mock_terminate_agreement_method.assert_not_called()
    mock_get_available_transfer_method.assert_called_once_with(
        agreement["id"], "225989344502", "651706759263"
    )
    mock_sync_responsibility_transfer_id_method.assert_called_once_with(agreement, "rt-8lr3q6sn")


def test_process_unhandled_exception_notifies(
    agreement,
    mock_get_available_transfer_method,
    mock_terminate_agreement_method,
    syncer,
    mock_send_exception,
):
    mock_get_available_transfer_method.return_value = None
    error_msg = "Test sync error"
    mock_terminate_agreement_method.side_effect = Exception(error_msg)

    syncer.process(agreement)  # act

    assert mock_get_available_transfer_method.call_count == 1
    mock_get_available_transfer_method.assert_called_once_with(
        agreement["id"], "225989344502", "651706759263"
    )
    mock_send_exception.assert_called_once()


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
        "AGR-2119-4550-8674-5962 - Inactive transfer",
        "Terminating agreement due to inactive transfer - "
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

    syncer.sync_responsibility_transfer_id(agreement, responsibility_transfer_id)  # act

    mock_update_agreement.assert_not_called()
    mock_send_exception.assert_not_called()


def test_sync_transfer_id_update(
    mock_send_exception, agreement_factory, mock_update_agreement, syncer
):
    agreement = agreement_factory()
    pma_account_id = "PMA-123456"

    syncer.sync_responsibility_transfer_id(agreement, pma_account_id)  # act

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

    syncer_dry_run.sync_responsibility_transfer_id(agreement, pma_account_id)  # act

    mock_update_agreement.assert_not_called()


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
    mock_update_agreement.side_effect = MPTError("error")
    mock_get_responsibility_transfer_id.return_value = "old"

    syncer.sync_responsibility_transfer_id(agreement, "new")  # act

    mock_send_exception.assert_called_once()


def test_get_mpa(agreement, syncer):
    result = syncer.get_mpa(agreement)

    assert result == "225989344502"


def test_get_pma(agreement, syncer):
    result = syncer.get_pma(agreement)

    assert result == "651706759263"


def test_synchronize_agreements_no_agreement_ids(
    agreement,
    mock_get_agreements_by_query,
    mock_get_available_transfer_method,
    mock_sync_responsibility_transfer_id_method,
    mock_awsclient,
    mock_get_linked_accounts_with_usage,
    mpt_client,
):
    mock_get_agreements_by_query.return_value = [agreement]
    mock_get_available_transfer_method.return_value = {
        "Id": "rt-8lr3q6sn",
        "Status": ResponsibilityTransferStatus.ACCEPTED.value,
    }

    synchronize_agreements(mpt_client, [], ["PROD-123-456"], dry_run=False)  # act

    mock_get_agreements_by_query.assert_called_once()
    mock_get_available_transfer_method.assert_called_once()
