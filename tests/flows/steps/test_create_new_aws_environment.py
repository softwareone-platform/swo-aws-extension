import pytest

from swo_aws_extension.constants import (
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.create_new_aws_environment import CreateNewAWSEnvironment
from swo_aws_extension.flows.steps.errors import (
    QueryStepError,
    SkipStepError,
)
from swo_aws_extension.parameters import get_phase


def test_skip_phase_is_not_expected(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CreateNewAWSEnvironment(config).pre_step(context)


def test_pre_step_proceeds_when_phase_matches(
    fulfillment_parameters_factory, order_factory, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    CreateNewAWSEnvironment(config).pre_step(context)  # act

    assert context.order is not None


def test_process_raises_query_error_when_missing(
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
        order_parameters=order_parameters_factory(mpa_id=""),
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(QueryStepError) as error:
        CreateNewAWSEnvironment(config).process(mpt_client, context)

    assert error.value.template_id == OrderQueryingTemplateEnum.NEW_ACCOUNT_CREATION.value


def test_process_succeeds_when_mpa_exists(
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
    )
    context = PurchaseContext.from_order_data(order)

    CreateNewAWSEnvironment(config).process(mpt_client, context)  # act

    assert (
        "ORD-0792-5000-2253-4210 - Next - Create New AWS Environment completed successfully"
        in caplog.text
    )


def test_post_step_updates_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = CreateNewAWSEnvironment(config)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.create_new_aws_environment.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value
