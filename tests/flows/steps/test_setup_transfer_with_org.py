from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.setup_context import (
    SetupContextPurchaseTransferWithOrganizationStep,
)
from swo_aws_extension.parameters import get_phase


def test_transfer_with_org_step(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="",
            mpa_account_id="",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="111111111111",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )

    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)
    step(mpt_client_mock, context, next_step_mock)
    mpt_client_mock.put.assert_called_once()  # Setting up phase
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_transfer_with_org_step_with_mpa(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="",
            mpa_account_id="111111111111",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="111111111111",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    setup_aws_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context."
        "SetupContextPurchaseTransferWithOrganizationStep.setup_aws"
    )
    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)
    step(mpt_client_mock, context, next_step_mock)
    mpt_client_mock.put.assert_called_once()  # Setting up phase
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    setup_aws_mock.assert_called_with(context)


def test_setup_querying(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION,
            mpa_account_id="",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )

    def return_order(client, order):
        return order

    switch_order_to_query_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.switch_order_to_query",
        side_effect=return_order,
    )
    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)
    step(mpt_client_mock, context, next_step_mock)
    switch_order_to_query_mock.assert_called_once()
    next_step_mock.assert_not_called()


def test_skip_purchase(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION,
            mpa_account_id="",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        ),
    )

    def return_order(client, order):
        return order

    get_phase_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_phase",
        side_effect=return_order,
    )
    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)
    step(mpt_client_mock, context, next_step_mock)
    next_step_mock.assert_called_once()
    get_phase_mock.assert_not_called()  # first call on processing the step


def test_skip_change(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        order_type=ORDER_TYPE_CHANGE,
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION,
            mpa_account_id="",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        ),
    )

    def return_order(client, order):
        return order

    get_phase_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_phase",
        side_effect=return_order,
    )
    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)
    step(mpt_client_mock, context, next_step_mock)
    next_step_mock.assert_called_once()
    get_phase_mock.assert_not_called()  # first call on processing the step
