import pytest
from mpt_extension_sdk.flows.context import Context
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.fulfillment import pipelines
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import get_phase


def test_purchase_new_steps():
    expected_step_classes = [
        "SetupContext",
        "ValidateOrder",
        "CRMTicketNewAccount",
        "CreateNewAWSEnvironment",
        "CreateBillingTransferInvitation",
        "CheckBillingTransferInvitation",
        "ConfigureAPNProgram",
        "CreateChannelHandshake",
        "CheckChannelHandshakeStatus",
        "CheckCustomerRoles",
        "CRMTicketOrderFail",
        "OnboardServices",
        "CheckOnboardStatus",
        "CreateSubscription",
        "ContractCardStep",
        "SWOJobStep",
        "CRMTicketPLS",
        "CRMTicketOnboardServices",
        "CompleteOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.purchase_new_aws_environment.queue]

    assert result == expected_step_classes


def test_purchase_existing_steps():
    expected_step_classes = [
        "SetupContext",
        "ValidateOrder",
        "CreateBillingTransferInvitation",
        "CheckBillingTransferInvitation",
        "ConfigureAPNProgram",
        "CreateChannelHandshake",
        "CheckChannelHandshakeStatus",
        "CheckCustomerRoles",
        "CRMTicketOrderFail",
        "OnboardServices",
        "CheckOnboardStatus",
        "CreateSubscription",
        "ContractCardStep",
        "SWOJobStep",
        "CRMTicketPLS",
        "CRMTicketOnboardServices",
        "CompleteOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.purchase_existing_aws_environment.queue]

    assert result == expected_step_classes


def test_purchase_migration_steps():
    expected_step_classes = [
        "SetupContext",
        "ValidateOrder",
        "ValidateMigrationOrder",
        "CreateBillingTransferInvitation",
        "CheckBillingTransferInvitation",
        "ConfigureAPNProgram",
        "CreateChannelHandshake",
        "CheckChannelHandshakeStatus",
        "CreateSubscription",
        "CompleteOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.purchase_migration.queue]

    assert result == expected_step_classes


def _post_step_phase(mocker, step, module, order):
    mocker.patch(
        f"swo_aws_extension.flows.steps.{module}.update_order",
        side_effect=lambda _client, _order_id, **kwargs: {**order, **kwargs},
    )
    context = PurchaseContext.from_order_data(order)
    step.post_step(mocker.MagicMock(spec=MPTClient), context)
    return get_phase(context.order)


@pytest.mark.parametrize(
    ("pipeline_name", "expected_handshake_phase", "expected_subscription_phase"),
    [
        ("purchase_migration", PhasesEnum.CREATE_SUBSCRIPTION, PhasesEnum.COMPLETED),
        (
            "purchase_existing_aws_environment",
            PhasesEnum.CHECK_CUSTOMER_ROLES,
            PhasesEnum.PROJECT_CREATION,
        ),
    ],
)
def test_pipeline_phase_chain(
    mocker,
    order_factory,
    pipeline_name,
    expected_handshake_phase,
    expected_subscription_phase,
):
    pipeline = getattr(pipelines, pipeline_name)
    steps = {step.__class__.__name__: step for step in pipeline.queue}

    result = (
        _post_step_phase(
            mocker,
            steps["CheckChannelHandshakeStatus"],
            "check_channel_handshake_status",
            order_factory(),
        ),
        _post_step_phase(
            mocker, steps["CreateSubscription"], "create_subscription", order_factory()
        ),
    )

    assert result == (expected_handshake_phase.value, expected_subscription_phase.value)


def test_terminate_steps():
    expected_step_classes = [
        "SetupContext",
        "ValidateTerminationOrder",
        "TerminateResponsibilityTransferStep",
        "CRMTicketTerminateOrder",
        "WaitTerminateResponsibilityTransferStep",
        "TerminateFinOpsEntitlementStep",
        "CompleteTerminationOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.terminate.queue]

    assert result == expected_step_classes


def test_pipeline_error_handler(mocker):
    next_step_mock = mocker.MagicMock(spec=Step)
    context = Context({"id": "order-id"})
    error = ValueError("Test exception")
    one_time_notification_mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.pipelines.notify_one_time_error",
    )

    with pytest.raises(ValueError):
        pipelines.pipeline_error_handler(error, context, next_step_mock)  # act

    one_time_notification_mock.assert_called_once()
