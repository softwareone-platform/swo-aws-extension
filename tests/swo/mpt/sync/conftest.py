import datetime as dt

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.swo.mpt.sync.agreement_subscription_syncer import (
    AgreementSubscriptionsSyncer,
)
from swo_aws_extension.swo.mpt.sync.agreement_syncer import AgreementSyncer
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

_SYNCER_MOD = "swo_aws_extension.swo.mpt.sync.agreement_syncer"
_SUB_SYNCER_MOD = "swo_aws_extension.swo.mpt.sync.agreement_subscription_syncer"
_TRANSFERS_MOD = "swo_aws_extension.swo.mpt.sync.responsibility_transfers"


@pytest.fixture
def mock_terminate_subscription(mocker):
    mock_fn = mocker.patch(f"{_SYNCER_MOD}.terminate_subscription", autospec=True)
    mocker.patch(f"{_SUB_SYNCER_MOD}.terminate_subscription", new=mock_fn)
    return mock_fn


@pytest.fixture
def mock_send_exception(mocker):
    return mocker.patch(
        f"{_SYNCER_MOD}.TeamsNotificationManager.send_exception",
        spec=TeamsNotificationManager,
    )


@pytest.fixture
def mock_send_error(mocker):
    return mocker.patch(
        f"{_SYNCER_MOD}.TeamsNotificationManager.send_error",
        spec=TeamsNotificationManager,
    )


@pytest.fixture
def mock_send_warning(mocker):
    return mocker.patch(
        f"{_SYNCER_MOD}.TeamsNotificationManager.send_warning",
        spec=TeamsNotificationManager,
    )


@pytest.fixture
def mock_get_agreements_by_query(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.get_agreements_by_query", autospec=True)


@pytest.fixture
def mock_awsclient(mocker):
    mock = mocker.Mock(spec=AWSClient)
    mocker.patch(f"{_TRANSFERS_MOD}.AWSClient", return_value=mock)
    mocker.patch(f"{_SUB_SYNCER_MOD}.AWSClient", return_value=mock)
    return mock


@pytest.fixture
def mock_get_linked_accounts_with_usage(mocker):
    return mocker.patch(
        f"{_SUB_SYNCER_MOD}.get_linked_accounts_with_usage",
        return_value=[],
    )


@pytest.fixture
def mock_get_product_items_by_skus(mocker):
    return mocker.patch(
        f"{_SUB_SYNCER_MOD}.get_product_items_by_skus",
        return_value=[{"id": "ITM-1234-1234-1234-0010"}],
    )


@pytest.fixture
def mock_create_agreement_subscription(mocker):
    return mocker.patch(
        f"{_SUB_SYNCER_MOD}.create_agreement_subscription",
        return_value={"id": "SUB-NEW-0001"},
    )


@pytest.fixture
def mock_get_available_transfer_for_account(mocker):
    return mocker.patch(
        f"{_SYNCER_MOD}.get_available_transfer_for_account",
        spec=True,
    )


@pytest.fixture
def mock_terminate_agreement(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.AgreementSyncer.terminate_agreement", spec=True)


@pytest.fixture
def mock_sync_responsibility_transfer_id(mocker):
    return mocker.patch(
        f"{_SYNCER_MOD}.AgreementSyncer.sync_responsibility_transfer_id",
        spec=True,
    )


@pytest.fixture
def responsibility_transfer_factory():
    def factory(
        status="ACCEPTED",
        source="225989344502",
        target="651706759263",
        start_timestamp="2025-11-01T00:00:00Z",
        end_timestamp=None,
        transfer_id="rt-8lr3q6sn",
    ):
        transfer = {
            "Arn": "arn:aws:organizations::651706759263:transfer/o-g88u5pukze/billing/inbound/"
            "rt-8lr3q6sn",
            "Name": "AWS_Transfer_Billing_Test_2",
            "Id": transfer_id,
            "Type": "BILLING",
            "Status": status,
            "Source": {"ManagementAccountId": source},
            "Target": {"ManagementAccountId": target},
            "StartTimestamp": dt.datetime.fromisoformat(start_timestamp),
        }
        if end_timestamp:
            transfer["EndTimestamp"] = dt.datetime.fromisoformat(end_timestamp)
        return transfer

    return factory


@pytest.fixture
def mock_update_agreement(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.update_agreement", spec=True)


@pytest.fixture
def mock_update_agreement_subscription(mocker):
    return mocker.patch(f"{_SUB_SYNCER_MOD}.update_agreement_subscription", autospec=True)


@pytest.fixture
def mock_get_responsibility_transfer_id(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.get_responsibility_transfer_id")


@pytest.fixture
def mock_get_crm_terminate_order_ticket_id(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.get_crm_terminate_order_ticket_id")


@pytest.fixture
def mock_crm_service_client(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.get_service_client").return_value


@pytest.fixture
def mock_get_mpa_method(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.AgreementSyncer.get_mpa")


@pytest.fixture
def mock_get_available_transfer_method(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.AgreementSyncer.get_available_transfer")


@pytest.fixture
def mock_get_responsibility_transfers(mocker):
    return mocker.patch(f"{_TRANSFERS_MOD}.get_available_responsibility_transfers")


@pytest.fixture
def mock_logger(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.logger")


@pytest.fixture
def syncer(mpt_client):
    return AgreementSyncer(mpt_client, dry_run=False)


@pytest.fixture
def syncer_dry_run(mpt_client):
    return AgreementSyncer(mpt_client, dry_run=True)


@pytest.fixture
def subscription_syncer(mpt_client):
    return AgreementSubscriptionsSyncer(mpt_client, dry_run=False)


@pytest.fixture
def subscription_syncer_dry_run(mpt_client):
    return AgreementSubscriptionsSyncer(mpt_client, dry_run=True)


@pytest.fixture
def mock_agreement_syncer(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.AgreementSyncer", autospec=True)


@pytest.fixture
def mock_sync_responsibility_transfer_id_method(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.AgreementSyncer.sync_responsibility_transfer_id")


@pytest.fixture
def mock_terminate_agreement_method(mocker):
    return mocker.patch(f"{_SYNCER_MOD}.AgreementSyncer.terminate_agreement")
