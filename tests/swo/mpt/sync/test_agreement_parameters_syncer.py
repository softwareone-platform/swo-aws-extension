import datetime as dt

import pytest
from mpt_api_client.exceptions import MPTError


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
