from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE
from mpt_extension_sdk.mpt_http.base import MPTClient
from requests import Response

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
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="111111111111",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    template_response = Response()
    template_response._content = b'{"data": ["template"]}'
    template_response.status_code = 200
    mpt_client_mock.get = mocker.Mock(return_value=template_response)

    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext(aws_client=None, order=order)
    step(mpt_client_mock, context, next_step_mock)
    mpt_client_mock.put.assert_called_once()  # Setting up phase
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_transfer_with_org_step_with_mpa(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
    mpa_pool_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="",
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    template_response = Response()
    template_response._content = b'{"data": ["template"]}'
    template_response.status_code = 200
    mpt_client_mock.get = mocker.Mock(return_value=template_response)

    setup_aws_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_context."
        "SetupContextPurchaseTransferWithOrganizationStep.setup_aws"
    )
    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext.from_order_data(order)
    step(mpt_client_mock, context, next_step_mock)
    mpt_client_mock.put.assert_called_once()  # Setting up phase
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    setup_aws_mock.assert_called_with(context)


def test_setup_querying(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mock_switch_order_status_to_query,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION,
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )

    def return_order(client, order):
        return order

    step = SetupContextPurchaseTransferWithOrganizationStep(config, "role_name")
    context = PurchaseContext.from_order_data(order)
    step(mpt_client_mock, context, next_step_mock)
    mock_switch_order_status_to_query.assert_called_once()
    next_step_mock.assert_not_called()


def test_skip_purchase(
    mocker, config, order_factory, fulfillment_parameters_factory, order_parameters_factory
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION,
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
