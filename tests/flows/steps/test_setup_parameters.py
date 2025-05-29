from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps import SetParametersVisibleStep
from swo_aws_extension.parameters import (
    PARAM_PHASE_ORDERING,
    OrderParametersEnum,
)


def test_update_parameter_visibility(order_factory):
    step = SetParametersVisibleStep()

    parameter = {
        "id": "PAR-1234-5679",
        "name": "Account Name",
        "externalId": OrderParametersEnum.ACCOUNT_NAME,
        "value": "account_name",
        "constraints": {"hidden": True, "readonly": False, "required": False},
    }
    new_paramter = step.set_hidden_paramter(parameter)
    assert new_paramter["constraints"]["hidden"] is False

    parameter2 = {
        "id": "PAR-1234-5679",
        "name": "Account Name",
        "externalId": OrderParametersEnum.ACCOUNT_NAME,
        "value": "account_name",
    }
    new_paramter2 = step.set_hidden_paramter(parameter2)
    assert new_paramter2["constraints"]["hidden"] is False


def test_update_all_parameters_visibility(
    mocker, order_factory, mpt_client, update_order_side_effect_factory
):
    next_step = mocker.Mock()
    order = order_factory()
    update_order_mock = mocker.patch(
        "swo_aws_extension.flows.steps.setup_parameters.update_order",
        side_effect=update_order_side_effect_factory(order),
    )
    step = SetParametersVisibleStep()

    context = InitialAWSContext.from_order_data(order)
    step(mpt_client, context, next_step)
    update_order_mock.assert_called()
    next_step.assert_called_once_with(mpt_client, context)
    assert context.order["parameters"][PARAM_PHASE_ORDERING][0]["constraints"]["hidden"] is False
