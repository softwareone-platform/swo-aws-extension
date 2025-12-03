import botocore
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.setup_context import SetupContext


def test_setup_context_with_pma(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    aws_client_mock = mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    order = order_factory()
    updated_order = order_factory(
        order_factory(
            fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CREATE_ACCOUNT),
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_order",
        return_value=updated_order,
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    aws_client_mock.assert_called_once_with(
        config, context.pm_account_id, SWO_EXTENSION_MANAGEMENT_ROLE
    )


def test_setup_context_without_pma_exception(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(authorization_external_id="")
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_not_called()


def test_setup_context_invalid_aws_credentials(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    _, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    error_response = {
        "Error": {
            "Code": "InvalidIdentityToken",
            "Message": "No OpenIDConnect provider found in your account for https://sts.windows.net/0001/",
        }
    }
    mock_client.get_caller_identity.side_effect = botocore.exceptions.ClientError(
        error_response, "get_caller_identity"
    )
    one_time_notification_mock = mocker.patch(
        "swo_aws_extension.flows.steps.base.TeamsNotificationManager.notify_one_time_error",
    )
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_not_called()
    assert "failing to provide valid AWS credentials" in one_time_notification_mock.call_args[0][1]
