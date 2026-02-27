import datetime as dt

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.flows.jobs.invitations_report_creator import InvitationsReportCreator
from swo_aws_extension.swo.azure_blob_uploader import AzureBlobUploader
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

MODULE = "swo_aws_extension.flows.jobs.invitations_report_creator"


@pytest.fixture
def external_mocks(mocker):
    mock_aws_client = mocker.MagicMock(spec=AWSClient)
    mocker.patch(f"{MODULE}.AWSClient", autospec=True, return_value=mock_aws_client)

    mock_blob_uploader = mocker.MagicMock(spec=AzureBlobUploader)
    mock_blob_uploader.upload_and_get_sas_url.return_value = (
        "https://acc.blob.core.windows.net/container/blob.xlsx?sas-token"
    )
    mocker.patch(f"{MODULE}.AzureBlobUploader", autospec=True, return_value=mock_blob_uploader)

    mock_excel_builder_cls = mocker.patch(f"{MODULE}.ExcelReportBuilder", autospec=True)

    mock_teams = mocker.MagicMock(spec=TeamsNotificationManager)
    mocker.patch(f"{MODULE}.TeamsNotificationManager", autospec=True, return_value=mock_teams)

    return {
        "aws_client": mock_aws_client,
        "teams": mock_teams,
        "blob_uploader": mock_blob_uploader,
        "excel_builder": mock_excel_builder_cls.return_value,
    }


@pytest.fixture
def report_creator(mpt_client, config, external_mocks):
    return InvitationsReportCreator(
        mpt_client,
        ["PRD-1111-1111"],
        config=config,
    )


def _make_invitation(
    invitation_id="rt-8lr3q6sn",
    status="Active",
    target_id="651706759263",
    source_id="111111111111",
    start=dt.datetime(2025, 1, 15, tzinfo=dt.UTC),
    end=dt.datetime(2025, 7, 15, tzinfo=dt.UTC),
):
    return {
        "Id": invitation_id,
        "Status": status,
        "Target": {"ManagementAccountId": target_id},
        "Source": {"ManagementAccountId": source_id},
        "StartTimestamp": start,
        "EndTimestamp": end,
    }


def _patch_authorizations_and_agreements(
    mocker, report_creator, authorizations, agreements, orders
):
    mocker.patch(f"{MODULE}.get_authorizations", autospec=True, return_value=authorizations)
    mocker.patch(f"{MODULE}.get_agreements_by_query", autospec=True, return_value=agreements)
    mocker.patch(f"{MODULE}.get_orders_by_query", autospec=True, return_value=orders)


def test_create_and_notify_teams_happy_path(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            customer_roles_deployed="yes",
            channel_handshake_approved="yes",
        ),
        ordering_parameters=order_parameters_factory(
            mpa_id="111111111111",
            support_type="Partner Led Support",
        ),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            customer_roles_deployed="yes",
            channel_handshake_approved="yes",
        ),
    )
    invitation = _make_invitation()
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = [invitation]

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()
    external_mocks["excel_builder"].build_from_rows.assert_called_once()
    built_rows = external_mocks["excel_builder"].build_from_rows.call_args[0][0]
    assert len(built_rows) == 1
    expected_row = [
        "651706759263",
        "111111111111",
        "rt-8lr3q6sn",
        "Active",
        agreement["id"],
        agreement["name"],
        "PRD-1111-1111",
        "",
        "Partner Led Support",
        "Yes",
        "Yes",
        "2025-01-15",
        "2025-07-15",
    ]
    assert built_rows[0] == expected_row
    external_mocks["teams"].send_success.assert_called_once()
    call_args = external_mocks["teams"].send_success.call_args
    assert "AWS Billing Transfer Invitations Report" in call_args.args[0]
    button = call_args.kwargs["button"]
    assert button.label == "Download report"
    assert "sas-token" in button.url


def test_no_authorizations(mocker, report_creator, external_mocks):
    _patch_authorizations_and_agreements(mocker, report_creator, [], [], [])

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()
    assert "0" in external_mocks["teams"].send_success.call_args.args[1]


def test_aws_error_sends_teams_error_and_continues(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-ok",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-ok",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
    )
    authorizations = [
        {"id": "AUT-FAIL", "externalIds": {"operations": "111"}},
        {"id": "AUT-OK", "externalIds": {"operations": "222"}},
    ]
    mocker.patch(f"{MODULE}.get_authorizations", autospec=True, return_value=authorizations)
    ok_client = mocker.MagicMock(spec=AWSClient)
    ok_client.get_inbound_responsibility_transfers.return_value = []
    mocker.patch(f"{MODULE}.AWSClient", side_effect=[AWSError("boom"), ok_client])
    mocker.patch(f"{MODULE}.get_agreements_by_query", autospec=True, return_value=[agreement])
    mocker.patch(f"{MODULE}.get_orders_by_query", autospec=True, return_value=[order])

    report_creator.create_and_notify_teams()  # act

    external_mocks["teams"].send_error.assert_called_once()
    external_mocks["teams"].send_success.assert_called_once()


def test_invitation_without_matching_agreement(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-other",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-other",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
    )
    invitation = _make_invitation(invitation_id="rt-unmatched")
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = [invitation]

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_agreement_without_matching_invitation(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-orphan",
            customer_roles_deployed="yes",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(mpa_id="111111111111"),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-orphan",
            customer_roles_deployed="yes",
            channel_handshake_approved="no",
        ),
    )
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = []

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_invitation_with_no_dates(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
    )
    invitation = _make_invitation(start=None, end=None)
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = [invitation]

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_agreement_with_none_authorization(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-x",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(mpa_id="mpa-123", support_type="PLS"),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-x",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
    )
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = []

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_agreement_with_none_mpa_account_id(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-y",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-y",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
    )
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = []

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_unmatched_invitation_with_no_dates(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-other",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(),
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-other",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
    )
    invitation = _make_invitation(invitation_id="rt-no-match", start=None, end=None)
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker, report_creator, authorizations, [agreement], [order]
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = [invitation]

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_invitation_uses_order_data_when_agreement_has_no_matching_transfer_id(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement_without_transfer_id = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(support_type="Basic Support"),
    )
    order_with_transfer_id = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-from-order",
            customer_roles_deployed="yes",
            channel_handshake_approved="yes",
        ),
        order_parameters=order_parameters_factory(support_type="Enterprise On-Ramp"),
    )
    invitation = _make_invitation(invitation_id="rt-from-order")
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker,
        report_creator,
        authorizations,
        [agreement_without_transfer_id],
        [order_with_transfer_id],
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = [invitation]

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()


def test_order_without_transfer_id_is_skipped(
    mocker,
    report_creator,
    external_mocks,
    agreement_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="",
            customer_roles_deployed="no",
            channel_handshake_approved="no",
        ),
        ordering_parameters=order_parameters_factory(),
    )
    order_without_transfer_id = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="",
            customer_roles_deployed="yes",
            channel_handshake_approved="yes",
        ),
        order_parameters=order_parameters_factory(support_type="Basic Support"),
    )
    invitation = _make_invitation(invitation_id="rt-invitation-only")
    authorizations = [{"id": "AUT-1", "externalIds": {"operations": "651706759263"}}]
    _patch_authorizations_and_agreements(
        mocker,
        report_creator,
        authorizations,
        [agreement],
        [order_without_transfer_id],
    )
    external_mocks["aws_client"].get_inbound_responsibility_transfers.return_value = [invitation]

    report_creator.create_and_notify_teams()  # act

    external_mocks["blob_uploader"].upload_and_get_sas_url.assert_called_once()
