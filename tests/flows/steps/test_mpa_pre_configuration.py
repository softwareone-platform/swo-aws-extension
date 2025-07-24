from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import AccountTypesEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.mpa_pre_configuration import MPAPreConfiguration
from swo_aws_extension.parameters import set_phase


def test_mpa_pre_configuration_phase_preconfig_mpa(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory, roots_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.PRECONFIGURATION_MPA.value
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_organization.return_value = {"Organization": {"Id": "test_organization"}}
    mock_client.list_roots.return_value = roots_factory()
    mock_client.enable_policy_type.return_value = roots_factory()

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.mpa_pre_configuration.update_order",
    )

    mpa_pre_config = MPAPreConfiguration()

    mpa_pre_config(mpt_client_mock, context, next_step_mock)

    mock_client.create_organization.assert_called_once_with(FeatureSet="ALL")
    mock_client.activate_organizations_access.assert_called_once_with()
    mock_client.list_roots.assert_called_once_with()
    mock_client.enable_policy_type.assert_called_once_with(
        RootId="root_id", PolicyType="SERVICE_CONTROL_POLICY"
    )
    assert (
        context.order["parameters"]
        == set_phase(order, PhasesEnum.CREATE_ACCOUNT.value)["parameters"]
    )

    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_mpa_pre_configuration_phase_not_preconfig_mpa(
    mocker, order_factory, config, aws_client_factory
):
    order = order_factory()

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    mpa_pre_config = MPAPreConfiguration()
    mpa_pre_config(mpt_client_mock, context, next_step_mock)

    mock_client.create_organization.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_mpa_pre_configuration_phase_preconfig_mpa_next_step_transfer(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    roots_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.PRECONFIGURATION_MPA.value
        ),
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.create_organization.return_value = {"Organization": {"Id": "test_organization"}}
    mock_client.list_roots.return_value = roots_factory()
    mock_client.enable_policy_type.return_value = roots_factory()

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.mpa_pre_configuration.update_order",
    )

    mpa_pre_config = MPAPreConfiguration()

    mpa_pre_config(mpt_client_mock, context, next_step_mock)

    mock_client.create_organization.assert_called_once_with(FeatureSet="ALL")
    mock_client.list_roots.assert_called_once_with()
    mock_client.enable_policy_type.assert_called_once_with(
        RootId="root_id", PolicyType="SERVICE_CONTROL_POLICY"
    )
    assert (
        context.order["parameters"]
        == set_phase(order, PhasesEnum.TRANSFER_ACCOUNT.value)["parameters"]
    )
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
