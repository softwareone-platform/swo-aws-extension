from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import AssignTransferMPAStep
from swo_aws_extension.parameters import get_phase


def test_assign_transfer_mpa_first_run(
    mocker,
    config,
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
):
    """
    First run moves the (order parameter) master_payer_id
    to (fulfillment parameter) mpa_account_id
    """
    mpt_client_mock = mocker.Mock(spec=MPTClient)

    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value,
        ),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )

    aws_client, aws_mock = aws_client_factory(config, "test_account_id", "test_role_name")
    context = PurchaseContext.from_order_data(order)
    context.aws_client = aws_client

    aws_mock.describe_organization.return_value = {
        "Organization": {
            "MasterAccountArn": "",
            "MasterAccountId": "123456789012",
        }
    }
    mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.update_agreement",
        return_value=agreement_factory(vendor_id="123456789012"),
    )

    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    assert context.mpa_account == ""
    step = AssignTransferMPAStep(config, "role_name")
    next_step_mock = mocker.Mock()
    step(mpt_client_mock, context, next_step_mock)
    assert context.mpa_account == "123456789012"
    next_step_mock.assert_called_once()
    mpt_client_mock.put.assert_called()
    assert get_phase(context.order) == PhasesEnum.PRECONFIGURATION_MPA


def test_assign_transfer_initialize_aws(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value,
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )
    context = PurchaseContext.from_order_data(order)
    context.aws_client = None
    step = AssignTransferMPAStep(config, "role_name")

    def mock_setup_aws(context):
        context.aws_client = aws_client

    next_step_mock = mocker.Mock()
    mock_steup_aws = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.AssignTransferMPAStep.setup_aws",
        side_effect=mock_setup_aws,
    )
    step(mpt_client_mock, context, next_step_mock)
    mock_steup_aws.assert_called_once()
    assert get_phase(context.order) == PhasesEnum.PRECONFIGURATION_MPA
    next_step_mock.assert_called_once()


def test_assign_transfer_failed_aws_access(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value,
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )
    context = PurchaseContext.from_order_data(order)
    context.aws_client = None
    step = AssignTransferMPAStep(config, "role_name")

    next_step_mock = mocker.Mock()
    mock_steup_aws = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.AssignTransferMPAStep.setup_aws",
        side_effect=AWSError("301", "Failed to assume role"),
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.send_error",
    )
    step(mpt_client_mock, context, next_step_mock)
    mock_steup_aws.assert_called_once()
    assert get_phase(context.order) == PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION
    next_step_mock.assert_not_called()
    expected_error_title = (
        "Transfer with Organization MPA: 123456789012 failed to retrieve credentials."
    )
    expected_message = (
        "The transfer with organization Master Payer Account 123456789012 is failing "
        "with error: ('301', 'Failed to assume role')"
    )
    mock_send_error.assert_called_once_with(expected_error_title, expected_message)


def test_skip_by_phase(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    mock_validate = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.AssignTransferMPAStep.validate_mpa_credentials",
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value,
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        ),
    )
    context = PurchaseContext(aws_client=None, order=order)
    step = AssignTransferMPAStep(config, "role_name")
    step(mpt_client_mock, context, next_step_mock)
    mock_validate.assert_not_called()  # First method in step processing
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_skip_not_transfer(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    agreement_factory,
):
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    mock_validate = mocker.patch(
        "swo_aws_extension.flows.steps.assign_mpa.AssignTransferMPAStep.validate_mpa_credentials",
    )
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            master_payer_id="123456789012",
            transfer_type="",
        ),
    )
    context = PurchaseContext(aws_client=None, order=order)
    step = AssignTransferMPAStep(config, "role_name")
    step(mpt_client_mock, context, next_step_mock)
    mock_validate.assert_not_called()  # First method in step processing
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
