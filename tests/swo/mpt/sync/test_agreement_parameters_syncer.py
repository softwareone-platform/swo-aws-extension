import datetime as dt

import pytest
from freezegun import freeze_time
from mpt_api_client.exceptions import MPTError

from swo_aws_extension.aws.models import ServiceTermRenewal


def test_parameters_syncer_process_backfills_parameters(
    mocker,
    agreement_factory,
    fulfillment_parameters_factory,
    mock_get_fixed_commitment_end_date,
    mock_update_agreement,
    parameters_syncer,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", channel_handshake_id="hs-123456"
        )
    )
    mock_get_fixed_commitment_end_date.return_value = dt.date.fromisoformat("2027-02-01")

    parameters_syncer.process(agreement)  # act

    assert mock_update_agreement.call_args_list == [
        mocker.call(
            parameters_syncer.mpt_client,
            agreement["id"],
            parameters={
                "fulfillment": [
                    {"externalId": "billingTransferAcceptanceDate", "value": "2026-02-01"}
                ]
            },
        ),
        mocker.call(
            parameters_syncer.mpt_client,
            agreement["id"],
            parameters={
                "fulfillment": [{"externalId": "handshakeExpirationDate", "value": "2027-02-01"}]
            },
        ),
    ]


def test_sync_billing_transfer_acceptance_date_update(
    agreement, mock_update_agreement, parameters_syncer
):
    parameters_syncer.sync_billing_transfer_acceptance_date(agreement, "2026-02-01")  # act

    mock_update_agreement.assert_called_once_with(
        parameters_syncer.mpt_client,
        agreement["id"],
        parameters={
            "fulfillment": [{"externalId": "billingTransferAcceptanceDate", "value": "2026-02-01"}]
        },
    )


@pytest.mark.parametrize(
    ("saved_acceptance_date", "acceptance_date"),
    [
        ("2026-01-15", "2026-02-01"),
        ("", None),
    ],
)
def test_sync_billing_transfer_acceptance_date_skips(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_update_agreement,
    mock_send_warning,
    parameters_syncer,
    saved_acceptance_date,
    acceptance_date,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            billing_transfer_acceptance_date=saved_acceptance_date
        )
    )

    parameters_syncer.sync_billing_transfer_acceptance_date(agreement, acceptance_date)  # act

    mock_update_agreement.assert_not_called()


def test_sync_billing_transfer_acceptance_date_error(
    agreement, mock_update_agreement, mock_send_exception, parameters_syncer
):
    mock_update_agreement.side_effect = MPTError("error")

    parameters_syncer.sync_billing_transfer_acceptance_date(agreement, "2026-02-01")  # act

    mock_send_exception.assert_called_once_with(
        f"{agreement['id']} - Synchronize billing transfer acceptance date",
        "Failed to update agreement with billing transfer acceptance date 2026-02-01",
    )


def test_sync_handshake_expiration_date_update(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_get_fixed_commitment_end_date,
    mock_update_agreement,
    parameters_syncer,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", channel_handshake_id="hs-123456"
        )
    )
    mock_get_fixed_commitment_end_date.return_value = dt.date.fromisoformat("2027-02-01")

    parameters_syncer.sync_handshake_expiration_date(agreement)  # act

    mock_update_agreement.assert_called_once_with(
        parameters_syncer.mpt_client,
        agreement["id"],
        parameters={
            "fulfillment": [{"externalId": "handshakeExpirationDate", "value": "2027-02-01"}]
        },
    )
    mock_get_fixed_commitment_end_date.assert_called_once_with(
        agreement["id"], "rel-123456", "hs-123456"
    )


@pytest.mark.parametrize(
    "factory_kwargs",
    [
        {"relationship_id": "", "channel_handshake_id": "hs-123456"},
        {"relationship_id": "rel-123456", "channel_handshake_id": ""},
        {
            "relationship_id": "rel-123456",
            "channel_handshake_id": "hs-123456",
            "handshake_expiration_date": "2027-01-01",
        },
    ],
)
def test_sync_handshake_expiration_date_skips_lookup(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_get_fixed_commitment_end_date,
    mock_update_agreement,
    parameters_syncer,
    factory_kwargs,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(**factory_kwargs)
    )

    parameters_syncer.sync_handshake_expiration_date(agreement)  # act

    assert (
        mock_get_fixed_commitment_end_date.called,
        mock_update_agreement.called,
    ) == (False, False)


def test_sync_handshake_expiration_date_no_fixed_commitment(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_get_fixed_commitment_end_date,
    mock_update_agreement,
    parameters_syncer,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", channel_handshake_id="hs-123456"
        )
    )
    mock_get_fixed_commitment_end_date.return_value = None

    parameters_syncer.sync_handshake_expiration_date(agreement)  # act

    mock_update_agreement.assert_not_called()


def test_sync_billing_transfer_acceptance_date_warns_without_start_date(
    mocker, caplog, agreement, mock_update_agreement, mock_send_warning, parameters_syncer
):
    message = "Billing transfer has no start date; acceptance date not set"

    parameters_syncer.sync_billing_transfer_acceptance_date(agreement, None)  # act

    assert (
        [(record.levelname, record.getMessage()) for record in caplog.records],
        mock_send_warning.call_args_list,
    ) == (
        [("WARNING", message)],
        [mocker.call(f"{agreement['id']} - Synchronize billing transfer acceptance date", message)],
    )


def test_parameters_syncer_process_renews_service_term_after_backfill(
    mocker, agreement, parameters_syncer
):
    sync_steps = mocker.Mock()
    for step in (
        "sync_billing_transfer_acceptance_date",
        "sync_handshake_expiration_date",
        "renew_expired_service_term",
    ):
        sync_steps.attach_mock(mocker.patch.object(parameters_syncer, step, autospec=True), step)

    parameters_syncer.process(agreement)  # act

    assert sync_steps.mock_calls == [
        mocker.call.sync_billing_transfer_acceptance_date(agreement, "2026-02-01"),
        mocker.call.sync_handshake_expiration_date(agreement),
        mocker.call.renew_expired_service_term(agreement),
    ]


@freeze_time("2026-11-02T12:00:00Z")
@pytest.mark.parametrize(("is_accepted", "approved"), [(False, "no"), (True, "yes")])
def test_renew_expired_service_term(
    mocker,
    agreement_factory,
    fulfillment_parameters_factory,
    mock_send_service_term_renewal,
    mock_update_agreement,
    parameters_syncer,
    is_accepted,
    approved,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456",
            channel_handshake_id="hs-123456",
            channel_handshake_approved="yes",
            handshake_expiration_date="2026-11-01",
        )
    )
    mock_send_service_term_renewal.return_value = ServiceTermRenewal(
        "hs-654321", is_accepted=is_accepted
    )

    parameters_syncer.renew_expired_service_term(agreement)  # act

    assert (
        mock_send_service_term_renewal.call_args_list,
        mock_update_agreement.call_args_list,
    ) == (
        [mocker.call(agreement["id"], "651706759263", "rel-123456")],
        [
            mocker.call(
                parameters_syncer.mpt_client,
                agreement["id"],
                parameters={
                    "fulfillment": [
                        {"externalId": "channelHandshakeId", "value": "hs-654321"},
                        {"externalId": "handshakeExpirationDate", "value": ""},
                        {"externalId": "channelHandshakeApproved", "value": approved},
                    ]
                },
            )
        ],
    )


@freeze_time("2026-11-02T12:00:00Z")
@pytest.mark.parametrize(
    "expiration_date",
    ["", "2026-11-02", "2027-02-01", "not-a-date"],
)
def test_renew_expired_service_term_skips_unexpired_term(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_send_service_term_renewal,
    mock_update_agreement,
    parameters_syncer,
    expiration_date,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", handshake_expiration_date=expiration_date
        )
    )

    parameters_syncer.renew_expired_service_term(agreement)  # act

    assert (mock_send_service_term_renewal.called, mock_update_agreement.called) == (False, False)


@freeze_time("2026-11-02T12:00:00Z")
def test_renew_expired_service_term_without_relationship(
    mocker,
    agreement_factory,
    fulfillment_parameters_factory,
    mock_send_service_term_renewal,
    mock_send_warning,
    parameters_syncer,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            handshake_expiration_date="2026-11-01"
        )
    )

    parameters_syncer.renew_expired_service_term(agreement)  # act

    assert (mock_send_service_term_renewal.called, mock_send_warning.call_args_list) == (
        False,
        [
            mocker.call(
                f"{agreement['id']} - Service term renewal",
                "Service term has expired but the relationship ID is missing",
            )
        ],
    )


@freeze_time("2026-11-02T12:00:00Z")
def test_renew_expired_service_term_dry_run(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_send_service_term_renewal,
    parameters_syncer_dry_run,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", handshake_expiration_date="2026-11-01"
        )
    )

    parameters_syncer_dry_run.renew_expired_service_term(agreement)  # act

    mock_send_service_term_renewal.assert_not_called()


@freeze_time("2026-11-02T12:00:00Z")
def test_renew_expired_service_term_handshake_not_created(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_send_service_term_renewal,
    mock_update_agreement,
    parameters_syncer,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", handshake_expiration_date="2026-11-01"
        )
    )
    mock_send_service_term_renewal.return_value = None

    parameters_syncer.renew_expired_service_term(agreement)  # act

    mock_update_agreement.assert_not_called()


@freeze_time("2026-11-02T12:00:00Z")
def test_renew_expired_service_term_update_error(
    agreement_factory,
    fulfillment_parameters_factory,
    mock_send_service_term_renewal,
    mock_update_agreement,
    mock_send_exception,
    parameters_syncer,
):
    agreement = agreement_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_id="rel-123456", handshake_expiration_date="2026-11-01"
        )
    )
    mock_send_service_term_renewal.return_value = ServiceTermRenewal("hs-654321", is_accepted=False)
    mock_update_agreement.side_effect = MPTError("error")

    parameters_syncer.renew_expired_service_term(agreement)  # act

    mock_send_exception.assert_called_once_with(
        f"{agreement['id']} - Service term renewal",
        "Failed to update agreement with the renewed service term channel handshake hs-654321",
    )
