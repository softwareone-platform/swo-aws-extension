import pytest

from swo_aws_extension.constants import (
    OrderQueryingTemplateEnum,
    PhasesEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.check_billing_transfer_invitation import (
    CheckBillingTransferInvitation,
)
from swo_aws_extension.flows.steps.errors import (
    ConfigurationStepError,
    FailStepError,
    QueryStepError,
    SkipStepError,
)
from swo_aws_extension.parameters import get_phase


def test_skip_phase_is_not_expected(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CREATE_ACCOUNT)
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CheckBillingTransferInvitation(config).pre_step(context)


def test_configuration_error_missing_transfer_id(
    fulfillment_parameters_factory, order_factory, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(ConfigurationStepError):
        CheckBillingTransferInvitation(config).pre_step(context)


def test_process_transfer_accepted(
    order_factory, aws_client_factory, fulfillment_parameters_factory, config, mpt_client
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="RT-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "mpa-id", "role-name")
    context.aws_client = aws_client_mock
    aws_client_mock.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }

    CheckBillingTransferInvitation(config).process(mpt_client, context)  # act

    aws_client_mock.get_responsibility_transfer_details.assert_called_once_with(
        transfer_id="RT-123"
    )


def test_process_transfer_pending(
    order_factory, aws_client_factory, fulfillment_parameters_factory, config, mpt_client
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="RT-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "mpa-id", "role-name")
    context.aws_client = aws_client_mock
    aws_client_mock.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.REQUESTED}
    }

    with pytest.raises(QueryStepError) as error:
        CheckBillingTransferInvitation(config).process(mpt_client, context)

    assert error.value.template_id == OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS


def test_process_transfer_cancelled(
    order_factory, aws_client_factory, fulfillment_parameters_factory, config, mpt_client
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="RT-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "mpa-id", "role-name")
    context.aws_client = aws_client_mock
    aws_client_mock.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.CANCELED}
    }

    with pytest.raises(FailStepError):
        CheckBillingTransferInvitation(config).process(mpt_client, context)


def test_process_transfer_declined(
    order_factory, aws_client_factory, fulfillment_parameters_factory, config, mpt_client
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="RT-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "mpa-id", "role-name")
    context.aws_client = aws_client_mock
    aws_client_mock.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.DECLINED}
    }

    with pytest.raises(FailStepError):
        CheckBillingTransferInvitation(config).process(mpt_client, context)


def test_post_step_sets_phase_to_onboard_services(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION,
            responsibility_transfer_id="RT-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = CheckBillingTransferInvitation(config)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ONBOARD_SERVICES)
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.check_billing_transfer_invitation.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.ONBOARD_SERVICES
