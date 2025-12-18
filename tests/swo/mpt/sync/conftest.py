import datetime as dt

import pytest

from swo_aws_extension.aws.client import AWSClient


@pytest.fixture
def mock_terminate_subscription(mocker):
    return mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.terminate_subscription", autospec=True
    )


@pytest.fixture
def mock_send_exception(mocker):
    return mocker.patch("swo_aws_extension.swo.mpt.sync.syncer.send_exception", autospec=True)


@pytest.fixture
def mock_send_error(mocker):
    return mocker.patch("swo_aws_extension.swo.mpt.sync.syncer.send_error", autospec=True)


@pytest.fixture
def mock_send_warning(mocker):
    return mocker.patch("swo_aws_extension.swo.mpt.sync.syncer.send_warning", autospec=True)


@pytest.fixture
def mock_get_agreements_by_query(mocker):
    return mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.get_agreements_by_query", autospec=True
    )


@pytest.fixture
def mock_awsclient(mocker):
    mock = mocker.Mock(spec=AWSClient)
    mocker.patch("swo_aws_extension.swo.mpt.sync.syncer.AWSClient", return_value=mock)
    return mock


@pytest.fixture
def mock_get_latest_inbound_responsibility_transfers(mocker):
    return mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.get_latest_inbound_responsibility_transfers",
        spec=True,
    )


@pytest.fixture
def mock_terminate_agreement(mocker):
    return mocker.patch("swo_aws_extension.swo.mpt.sync.syncer.terminate_agreement", spec=True)


@pytest.fixture
def responsibility_transfer_factory():
    def _responsibility_transfer(
        status="ACCEPTED",
        source="225989344502",
        target="651706759263",
        start_timestamp="2025-11-01T00:00:00Z",
    ):
        return {
            "Arn": "arn:aws:organizations::651706759263:transfer/o-g88u5pukze/billing/inbound/"
            "rt-8lr3q6sn",
            "Name": "AWS_Transfer_Billing_Test_2",
            "Id": "rt-8lr3q6sn",
            "Type": "BILLING",
            "Status": status,
            "Source": {"ManagementAccountId": source},
            "Target": {"ManagementAccountId": target},
            "StartTimestamp": dt.datetime.fromisoformat(start_timestamp),
        }

    return _responsibility_transfer


@pytest.fixture
def mock_sync_responsibility_transfer_id(mocker):
    return mocker.patch(
        "swo_aws_extension.swo.mpt.sync.syncer.sync_responsibility_transfer_id", spec=True
    )


@pytest.fixture
def mock_update_agreement(mocker):
    return mocker.patch("swo_aws_extension.swo.mpt.sync.syncer.update_agreement", spec=True)
