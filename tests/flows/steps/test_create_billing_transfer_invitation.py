import pytest
from freezegun import freeze_time

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import OrderQueryingTemplateEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.create_billing_transfer_invitation import (
    CreateBillingTransferInvitation,
)
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    QueryStepError,
    SkipStepError,
)
from swo_aws_extension.parameters import get_phase, get_responsibility_transfer_id

START_TIMESTAMP = 1767225600


def test_skip_phase_is_not_expected(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CREATE_ACCOUNT)
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CreateBillingTransferInvitation(config).pre_step(context)


def test_already_processed_transfer_id_exists(
    order_factory, config, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="RT-123",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(AlreadyProcessedStepError):
        CreateBillingTransferInvitation(config).pre_step(context)

    assert get_phase(context.order) == PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION


def test_missing_mpa_id(
    order_factory, config, fulfillment_parameters_factory, order_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="",
        ),
        order_parameters=order_parameters_factory(
            mpa_id="",
        ),
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(QueryStepError) as error:
        CreateBillingTransferInvitation(config).process(context)

    assert error.value.template_id == OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID


@freeze_time("2025-12-22 00:00:00")
def test_create_transfer_billing_invitation(
    order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "mpa-id", "role-name")
    context.aws_client = aws_client_mock
    aws_client_mock.invite_organization_to_transfer_billing.return_value = {
        "Handshake": {
            "Resources": [
                {"Type": "RESPONSIBILITY_TRANSFER", "Value": "RT-123"},
            ]
        }
    }

    CreateBillingTransferInvitation(config).process(context)  # act

    assert get_responsibility_transfer_id(context.order) == "RT-123"
    relationship_name = f"Transfer Billing - {context.buyer['name']}"
    aws_client_mock.invite_organization_to_transfer_billing.assert_called_once_with(
        customer_id="651706759263",
        source_name=relationship_name,
        start_timestamp=START_TIMESTAMP,
    )


def test_create_transfer_billing_invitation_error(
    order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "mpa-id", "role-name")
    context.aws_client = aws_client_mock
    aws_client_mock.invite_organization_to_transfer_billing.side_effect = AWSError(
        "Invalid Master Payer Account ID"
    )

    with pytest.raises(QueryStepError) as error:
        CreateBillingTransferInvitation(config).process(context)

    assert error.value.template_id == OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID


def test_post_step_sets_phase(
    mocker, config, order_factory, fulfillment_parameters_factory, mpt_client
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
        )
    )
    context = PurchaseContext.from_order_data(order)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.create_billing_transfer_invitation.switch_order_status_to_query_and_notify",
        return_value=updated_order,
    )

    CreateBillingTransferInvitation(config).post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION
