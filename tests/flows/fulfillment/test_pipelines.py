import pytest
from mpt_extension_sdk.flows.context import Context
from mpt_extension_sdk.flows.pipeline import Step

from swo_aws_extension.flows.fulfillment import pipelines


def test_purchase_new_steps():
    expected_step_classes = [
        "SetupContext",
        "CreateNewAWSEnvironment",
        "CreateBillingTransferInvitation",
        "CheckBillingTransferInvitation",
        "OnboardServices",
        "CreateSubscription",
        "CompleteOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.purchase_new_aws_environment.queue]

    assert result == expected_step_classes


def test_purchase_existing_steps():
    expected_step_classes = [
        "SetupContext",
        "CreateBillingTransferInvitation",
        "CheckBillingTransferInvitation",
        "OnboardServices",
        "CreateSubscription",
        "CompleteOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.purchase_existing_aws_environment.queue]

    assert result == expected_step_classes


def test_terminate_steps():
    expected_step_classes = [
        "SetupContext",
        "TerminateResponsibilityTransferStep",
        "CompleteTerminationOrder",
    ]

    result = [step.__class__.__name__ for step in pipelines.terminate.queue]

    assert result == expected_step_classes


def test_pipeline_error_handler(mocker):
    next_step_mock = mocker.MagicMock(spec=Step)
    context = Context({"id": "order-id"})
    error = ValueError("Test exception")
    one_time_notification_mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.pipelines.TeamsNotificationManager.notify_one_time_error",
    )

    with pytest.raises(ValueError):
        pipelines.pipeline_error_handler(error, context, next_step_mock)  # act

    one_time_notification_mock.assert_called_once()
