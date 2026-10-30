import copy

import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.flows.steps.skip_phase import SkipPhaseStep
from swo_aws_extension.parameters import get_phase


@pytest.fixture
def skip_phase_step():
    return SkipPhaseStep(PhasesEnum.CHECK_CUSTOMER_ROLES, next_phase=PhasesEnum.CREATE_SUBSCRIPTION)


@pytest.fixture
def check_customer_roles_context(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CHECK_CUSTOMER_ROLES)
    )
    return PurchaseContext.from_order_data(order)


def test_pre_step_skips_wrong_phase(order_factory, fulfillment_parameters_factory, skip_phase_step):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        skip_phase_step.pre_step(context)


def test_pre_step_proceeds_when_phase_matches(check_customer_roles_context, skip_phase_step):
    skip_phase_step.pre_step(check_customer_roles_context)  # act

    assert get_phase(check_customer_roles_context.order) == PhasesEnum.CHECK_CUSTOMER_ROLES


def test_process_leaves_order_unchanged(check_customer_roles_context, skip_phase_step, mpt_client):
    original_order = copy.deepcopy(check_customer_roles_context.order)

    skip_phase_step.process(mpt_client, check_customer_roles_context)  # act

    assert check_customer_roles_context.order == original_order


def test_post_step_sets_next_phase(
    mocker, check_customer_roles_context, skip_phase_step, mpt_client
):
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.skip_phase.update_order",
        autospec=True,
        side_effect=lambda _client, _order_id, **kwargs: {
            **check_customer_roles_context.order,
            **kwargs,
        },
    )

    skip_phase_step.post_step(mpt_client, check_customer_roles_context)  # act

    mock_update.assert_called_once_with(
        mpt_client,
        check_customer_roles_context.order_id,
        parameters=check_customer_roles_context.order["parameters"],
    )
    assert get_phase(check_customer_roles_context.order) == PhasesEnum.CREATE_SUBSCRIPTION
