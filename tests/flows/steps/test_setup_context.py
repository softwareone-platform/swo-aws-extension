import pytest
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.setup_context import SetupContext, SetupPurchaseContext


def test_setup_context_with_pma(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    aws_client_mock = mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(pm_account_id="123456789123"),
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    aws_client_mock.assert_called_once_with(
        config, context.pm_account_id, SWO_EXTENSION_MANAGEMENT_ROLE
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_context_without_pma_exception(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(pm_account_id=""),
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    with pytest.raises(ValueError):
        step(mpt_client_mock, context, next_step_mock)  # act


def test_setup_purchase_context_with_pma(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    aws_client_mock = mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(pm_account_id="123456789123"),
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    aws_client_mock.assert_called_once_with(
        config, context.pm_account_id, SWO_EXTENSION_MANAGEMENT_ROLE
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_setup_purchase_context_without_pma(
    mocker, config, aws_client_factory, order_factory, fulfillment_parameters_factory
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    aws_client_mock = mocker.patch("swo_aws_extension.flows.steps.setup_context.AWSClient")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(pm_account_id=""),
    )
    context = PurchaseContext.from_order_data(order)
    step = SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    aws_client_mock.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
