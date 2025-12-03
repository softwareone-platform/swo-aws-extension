from botocore.exceptions import ClientError
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.errors import AirtableRecordNotFoundError
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.assign_pma import AssignPMA


def test_assign_pma_invalid_phase(mocker, config, order_factory, fulfillment_parameters_factory):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CREATE_ACCOUNT),
    )
    context = PurchaseContext.from_order_data(order)
    step = AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_called_once()


def test_assign_pma_already_assigned(mocker, config, order_factory, fulfillment_parameters_factory):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_PMA, pm_account_id="123456789123"
        ),
    )
    context = PurchaseContext.from_order_data(order)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT, pm_account_id="123456789123"
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.update_order",
        return_value=updated_order,
    )
    step = AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_called_once()
    assert context.phase == PhasesEnum.CREATE_ACCOUNT


def test_assign_pma(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    pma_table_factory,
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_PMA, pm_account_id=""
        ),
    )
    context = PurchaseContext.from_order_data(order)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT, pm_account_id="123456789123"
        ),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.update_order",
        return_value=updated_order,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.ProgramManagementAccountTable.get_by_authorization_and_currency_id",
        return_value=pma_table_factory(),
    )
    _, mock_client = aws_client_factory(config, "123456789123", SWO_EXTENSION_MANAGEMENT_ROLE)
    mock_client.get_caller_identity.return_value = {}
    step = AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_called_once()
    assert context.phase == PhasesEnum.CREATE_ACCOUNT
    assert context.pm_account_id == "123456789123"


def test_assign_pma_invalid_credentials(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    pma_table_factory,
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_PMA, pm_account_id=""
        ),
    )
    context = PurchaseContext.from_order_data(order)
    pm_account = pma_table_factory()
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.ProgramManagementAccountTable.get_by_authorization_and_currency_id",
        return_value=pm_account,
    )
    one_time_notification_mock = mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.notify_one_time_error_in_teams",
    )
    _, mock_client = aws_client_factory(config, "123456789123", SWO_EXTENSION_MANAGEMENT_ROLE)
    error_response = {
        "Error": {
            "Code": "InvalidIdentityToken",
            "Message": "No OpenIDConnect provider found in your account for https://sts.windows.net/0001/",
        }
    }
    mock_client.get_caller_identity.side_effect = ClientError(error_response, "get_caller_identity")
    step = AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_not_called()
    assert "No OpenIDConnect provider found" in one_time_notification_mock.call_args[0][1]


def test_assign_pma_not_found_error(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    pma_table_factory,
):
    mpt_client_mock = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_PMA, pm_account_id=""
        ),
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.ProgramManagementAccountTable.get_by_authorization_and_currency_id",
        side_effect=AirtableRecordNotFoundError("PMA not found"),
    )
    one_time_notification_mock = mocker.patch(
        "swo_aws_extension.flows.steps.assign_pma.notify_one_time_error_in_teams",
    )
    step = AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE)

    step(mpt_client_mock, context, next_step_mock)  # act

    next_step_mock.assert_not_called()
    assert "No Program Management Account found" in one_time_notification_mock.call_args[0][0]
