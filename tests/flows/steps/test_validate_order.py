import pytest
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.validate_order import ValidateOrder


def test_validate_order_fails_when_active_agreement_exists(
    mocker, order_factory, order_parameters_factory
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mock_fail = mocker.patch("swo_aws_extension.flows.steps.base.switch_order_status_to_failed")
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.has_previous_order",
        return_value=True,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.get_phase",
        return_value=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
    )
    context = PurchaseContext.from_order_data(order_factory())
    step = ValidateOrder()

    step(mock_client, context, next_step_mock)  # act

    assert mock_fail.call_args[0][2]["id"] == "AWS004"
    next_step_mock.assert_not_called()


def test_validate_order_proceeds_when_no_previous_agreement(
    mocker, order_factory, order_parameters_factory, buyer_factory
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.has_previous_order",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.get_phase",
        return_value=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
    )
    buyer = {**buyer_factory(), "externalIds": {"erpCustomer": "US-SCU-111111"}}
    context = PurchaseContext.from_order_data(order_factory(buyer=buyer))
    step = ValidateOrder()

    step(mock_client, context, next_step_mock)  # act

    next_step_mock.assert_called_once()


@pytest.mark.parametrize(
    "buyer_without_scu",
    [
        {"id": "BUY-1111-1111", "name": "A buyer"},
        {"id": "BUY-1111-1111", "name": "A buyer", "externalIds": None},
        {"id": "BUY-1111-1111", "name": "A buyer", "externalIds": {"erpCustomer": ""}},
    ],
)
def test_validate_order_stops_when_buyer_scu_is_missing(mocker, order_factory, buyer_without_scu):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mock_notify = mocker.patch("swo_aws_extension.flows.steps.base.notify_one_time_error")
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.has_previous_order",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.get_phase",
        return_value=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION,
    )
    context = PurchaseContext.from_order_data(order_factory(buyer=buyer_without_scu))
    step = ValidateOrder()

    step(mock_client, context, next_step_mock)  # act

    mock_notify.assert_called_once_with(
        "Buyer SCU is not set for order ORD-0792-5000-2253-4210",
        "Buyer SCU is not set for order ORD-0792-5000-2253-4210 (MPA 651706759263, "
        "buyer BUY-1111-1111)",
    )
    next_step_mock.assert_not_called()


def test_validate_order_skips_when_phase_does_not_match(mocker, order_factory):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mocker.patch(
        "swo_aws_extension.flows.steps.validate_order.get_phase",
        return_value="some_other_phase",
    )
    context = PurchaseContext.from_order_data(order_factory())
    step = ValidateOrder()

    step(mock_client, context, next_step_mock)  # act

    next_step_mock.assert_called_once()
