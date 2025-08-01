import copy
from copy import deepcopy

import botocore.exceptions
import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import AssignMPA, AssignSplitBillingMPA
from swo_aws_extension.notifications import Button
from swo_aws_extension.parameters import get_mpa_email, set_mpa_email, set_phase


def test_assign_mpa_phase_not_assign_mpa(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value),
        agreement=agreement_factory(vendor_id="123456789012"),
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)

    mock_client.get_caller_identity.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_assign_mpa_phase_mpa_already_assigned(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value),
        agreement=agreement_factory(vendor_id="123456789012"),
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    updated_order = set_phase(order, PhasesEnum.PRECONFIGURATION_MPA.value)
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
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    mpa_pool_factory,
    agreement_factory,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value),
        buyer=buyer,
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_caller_identity.return_value = {}

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    context.airtable_mpa = mpa_pool_factory()
    next_step_mock = mocker.Mock()

    def update_order_side_effect(*args, **kwargs):
        updated_order = copy.deepcopy(order)
        updated_order["parameters"] = kwargs["parameters"]
        return updated_order

    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_order",
        side_effect=update_order_side_effect,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_agreement",
        return_value=agreement_factory(vendor_id="123456789012"),
    )

    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_called_once()

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    assert get_mpa_email(context.order) == "test@email.com"
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )
    assert context.airtable_mpa.scu == context.buyer.get("externalIds", {}).get("erpCustomer", "")


def test_assign_mpa_phase_assign_mpa_credentials_error(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    mpa_pool_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value)
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

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    context.airtable_mpa = mpa_pool_factory()
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
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value)
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_caller_identity.return_value = {}

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    context.airtable_mpa = None
    next_step_mock = mocker.Mock()
    mocked_update_order = mocker.patch("swo_aws_extension.flows.steps.assign_mpa.update_order")
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocker.patch("swo_aws_extension.flows.steps.assign_mpa.send_error")

    mocked_pool_notification_model.first.return_value = None
    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_not_called()

    next_step_mock.assert_not_called()
    mocked_update_order.assert_not_called()


def test_assign_mpa_phase_not_mpa_account_notification_already_created(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    pool_notification_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value)
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_caller_identity.return_value = {}

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    context.airtable_mpa = None
    next_step_mock = mocker.Mock()
    mocked_update_order = mocker.patch("swo_aws_extension.flows.steps.assign_mpa.update_order")
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocker.patch("swo_aws_extension.flows.steps.assign_mpa.send_error")

    mocked_pool_notification_model.first.return_value = pool_notification_factory()
    assign_mpa = AssignMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)
    mock_client.get_caller_identity.assert_not_called()

    next_step_mock.assert_not_called()
    mocked_update_order.assert_not_called()


def test_assign_mpa_split_billing_valid_mpa(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
    order_parameters_factory,
    mpa_pool_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value),
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value, master_payer_id="123456789012"
        ),
    )
    initial_order = deepcopy(order)

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    updated_order = set_phase(order, PhasesEnum.CREATE_ACCOUNT.value)
    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_order",
        return_value=updated_order,
    )
    mocked_update_agreement = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_agreement",
        return_value=agreement_factory(vendor_id="123456789012"),
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.is_split_billing_mpa_id_valid",
        return_value=True,
    )

    assign_mpa = AssignSplitBillingMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)

    mock_client.get_caller_identity.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
    initial_order = set_phase(initial_order, PhasesEnum.CREATE_ACCOUNT.value)
    initial_order = set_mpa_email(initial_order, context.airtable_mpa.account_email)
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=initial_order["parameters"],
    )
    mocked_update_agreement.assert_called_once_with(
        mpt_client_mock,
        context.agreement["id"],
        externalIds={"vendor": "123456789012"},
    )


def test_assign_mpa_split_billing_invalid_mpa(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
    order_parameters_factory,
    mpa_pool_factory,
    mock_switch_order_status_to_query,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value),
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value, master_payer_id="invalid"
        ),
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    mocked_update_order = mocker.patch("swo_aws_extension.flows.steps.assign_mpa.update_order")

    mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.is_split_billing_mpa_id_valid",
        return_value=False,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.get_mpa_account",
        return_value=mpa_pool_factory(),
    )
    assign_mpa = AssignSplitBillingMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)

    mock_client.get_caller_identity.assert_not_called()
    next_step_mock.assert_not_called()
    mocked_update_order.assert_not_called()
    mock_switch_order_status_to_query.assert_called_once()


def test_assign_mpa_empty_country(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
    mpa_pool_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ASSIGN_MPA.value)
    )
    order["seller"]["address"]["country"] = ""

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.get_caller_identity.return_value = {}

    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client
    context.airtable_mpa = None
    next_step_mock = mocker.Mock()
    mocked_pool_notification_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_pool_notification_model",
        return_value=mocked_pool_notification_model,
    )
    mocked_pool_notification_model.first.return_value = None

    assign_mpa = AssignMPA(config, "test_role_name")
    with pytest.raises(ValueError) as e:
        assign_mpa(mpt_client_mock, context, next_step_mock)

    assert f"{context.order_id} - Seller country is not included in the order." in str(e.value)


def test_assign_split_billing_mpa_phase_not_assign_mpa(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value),
        agreement=agreement_factory(vendor_id="123456789012"),
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    assign_mpa = AssignSplitBillingMPA(config, "test_role_name")
    assign_mpa(mpt_client_mock, context, next_step_mock)

    mock_client.get_caller_identity.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
