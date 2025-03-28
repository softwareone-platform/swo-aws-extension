import botocore.exceptions
from swo.mpt.client import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import AssignMPA
from swo_aws_extension.notifications import Button
from swo_aws_extension.parameters import set_mpa_account_id, set_phase


def test_assign_mpa_phase_not_assign_mpa(mocker, order_factory, config, aws_client_factory):
    order = order_factory()

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)

    mock_client.get_caller_identity.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_assign_mpa_phase_mpa_already_assigned(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            mpa_account_id="test_mpa_account", phase=PhasesEnum.ASSIGN_MPA
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    updated_order = set_phase(order, PhasesEnum.PRECONFIGURATION_MPA)
    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_order",
        return_value=updated_order,
    )

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_not_called()

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )


def test_assign_mpa_phase_assign_mpa(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory, mpa_pool
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_MPA, mpa_account_id=""
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_caller_identity.return_value = {}

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    context.airtable_mpa = mpa_pool
    next_step_mock = mocker.Mock()

    updated_order = set_phase(order, PhasesEnum.PRECONFIGURATION_MPA)
    updated_order = set_mpa_account_id(updated_order, "Account Id")
    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_order",
        return_value=updated_order,
    )

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_called_once()

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )


def test_assign_mpa_phase_assign_mpa_credentials_error(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory, mpa_pool
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_MPA, mpa_account_id=""
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    error_response = {
        "Error": {
            "Code": "InvalidIdentityToken",
            "Message": "No OpenIDConnect provider found in your account for https://sts.windows.net/0001/",
        }
    }
    mock_client.get_caller_identity.side_effect = botocore.exceptions.ClientError(
        error_response, "get_caller_identity"
    )

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    context.airtable_mpa = mpa_pool
    next_step_mock = mocker.Mock()

    mocked_update_order = mocker.patch("swo_aws_extension.flows.steps.assign_mpa.update_order")
    mocked_send_error = mocker.patch("swo_aws_extension.flows.steps.assign_mpa.send_error")
    mocked_mpa_view_link = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.get_mpa_view_link",
        return_value="https://airtable.com/",
    )

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_called_once()

    next_step_mock.assert_not_called()
    mocked_update_order.assert_not_called()
    mocked_mpa_view_link.assert_called_once()
    error = (
        "AWS Client error: An error occurred (InvalidIdentityToken) when calling the "
        "get_caller_identity operation: No OpenIDConnect provider found in your "
        "account for https://sts.windows.net/0001/"
    )
    mocked_send_error.assert_called_once_with(
        f"Master Payer account {context.airtable_mpa.account_id} failed to retrieve credentials",
        f"The Master Payer Account {context.airtable_mpa.account_id} "
        f"is failing with error: {error}",
        button=Button("Open Master Payer Accounts View", "https://airtable.com/"),
    )


def test_assign_mpa_phase_not_mpa_account(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_MPA, mpa_account_id=""
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_caller_identity.return_value = {}

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    context.airtable_mpa = None
    next_step_mock = mocker.Mock()
    mocked_update_order = mocker.patch("swo_aws_extension.flows.steps.assign_mpa.update_order")

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_not_called()

    next_step_mock.assert_not_called()
    mocked_update_order.assert_not_called()
