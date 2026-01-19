import botocore
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    SWO_EXTENSION_MANAGEMENT_ROLE,
    AccountTypesEnum,
    OrderProcessingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.setup_context import SetupContext


def test_setup_context_with_pma(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    aws_client_mock = mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_processing_template_and_notify"
    )
    order = order_factory()
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
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
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    mock_teams_notification_manager,
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(authorization_external_id="")
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_not_called()
    assert mock_teams_notification_manager.mock_calls == [
        mocker.call(),
        mocker.call().notify_one_time_error(
            "Setup context",
            "SetupContextError - PMA account is required to setup AWS Client in context",
        ),
    ]


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
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_processing_template_and_notify"
    )
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_not_called()
    assert "failing to provide valid AWS credentials" in one_time_notification_mock.call_args[0][1]


def test_init_template_new_account(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    update_template_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_processing_template_and_notify"
    )
    order = order_factory(
        order_type="Purchase",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_order",
        return_value=order,
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    update_template_mock.assert_called_once_with(
        mpt_client_mock, context, OrderProcessingTemplateEnum.NEW_ACCOUNT
    )


def test_init_template_existing_account(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    update_template_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_processing_template_and_notify"
    )
    order = order_factory(
        order_type="Purchase",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value,
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_order",
        return_value=order,
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    update_template_mock.assert_called_once_with(
        mpt_client_mock, context, OrderProcessingTemplateEnum.EXISTING_ACCOUNT
    )


def test_init_template_terminate(mocker, config, order_factory, fulfillment_parameters_factory):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    update_template_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_processing_template_and_notify"
    )
    order = order_factory(
        order_type="Termination",
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.COMPLETED.value,
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_order",
        return_value=order,
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    update_template_mock.assert_called_once_with(
        mpt_client_mock, context, OrderProcessingTemplateEnum.TERMINATE
    )


def test_init_template_skipped_when_same(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    template_factory,
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    update_template_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_processing_template_and_notify"
    )
    template = template_factory(name=OrderProcessingTemplateEnum.EXISTING_ACCOUNT.value)
    order = order_factory(
        order_type="Purchase",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value
        ),
        template=template,
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.update_order",
        return_value=order,
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    update_template_mock.assert_not_called()
