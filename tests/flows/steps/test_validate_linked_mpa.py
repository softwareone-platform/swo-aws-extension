from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import ValidateLinkedMPAStep
from swo_aws_extension.parameters import get_phase


def test_validate_linked_mpa_first_run(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    """
    First run moves the (order parameter) master_payer_id
    to (fulfillment parameter) mpa_account_id
    """
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_MPA,
            mpa_account_id="",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="111111111111",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    context = PurchaseContext(aws_client=None, order=order)

    assert get_phase(context.order) == PhasesEnum.ASSIGN_MPA
    assert context.mpa_account == ""
    step = ValidateLinkedMPAStep()
    next_step_mock = mocker.Mock()
    step(mpt_client_mock, context, next_step_mock)
    assert context.mpa_account == "111111111111"
    mpt_client_mock.put.assert_called_once()
    assert get_phase(context.order) == PhasesEnum.ASSIGN_MPA
    next_step_mock.assert_not_called()


def test_validate_linked_mpa_second_run(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, aws_mock = aws_client_factory(config, "test_account_id", "test_role_name")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_MPA,
            mpa_account_id="111111111111",
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="111111111111",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    context = PurchaseContext(aws_client=aws_client, order=order)
    step = ValidateLinkedMPAStep()
    next_step_mock = mocker.Mock()
    step(mpt_client_mock, context, next_step_mock)
    mpt_client_mock.put.assert_called_once()
    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTIONS
    next_step_mock.assert_called_once()
