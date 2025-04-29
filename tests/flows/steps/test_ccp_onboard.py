from mpt_extension_sdk.mpt_http.base import MPTClient
from requests import HTTPError, JSONDecodeError

from swo_aws_extension.constants import CCPOnboardStatusEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import CCPOnboard
from swo_aws_extension.parameters import set_ccp_engagement_id, set_phase
from swo_crm_service_client import CRMServiceClient


def test_onboard_ccp_customer(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    ccp_client,
    mpa_pool_factory,
    mock_onboard_customer_response,
    onboard_customer_factory,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CCP_ONBOARD),
        agreement=agreement_factory(vendor_id="123456789012"),
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    mocked_onboard_customer = mocker.patch(
        "swo_ccp_client.client.CCPClient.onboard_customer",
        return_value=mock_onboard_customer_response,
    )
    updated_order = set_ccp_engagement_id(order, mock_onboard_customer_response[1]["id"])
    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.ccp_onboard.update_order",
        return_value=updated_order,
    )

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )

    mocked_master_payer_account_pool_model.first.return_value = mpa_pool_factory()

    ccp_onboard = CCPOnboard(config)
    ccp_onboard(mpt_client_mock, context, next_step_mock)
    mocked_onboard_customer.assert_called_once_with(onboard_customer_factory())
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )
    next_step_mock.assert_not_called()


def test_check_onboard_ccp_status_running(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    ccp_client,
    onboard_customer_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CCP_ONBOARD, ccp_engagement_id="123123"
        )
    )
    mocked_onboard_status = mocker.patch(
        "swo_ccp_client.client.CCPClient.get_onboard_status",
        return_value=onboard_customer_status_factory(CCPOnboardStatusEnum.RUNNING),
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    ccp_onboard = CCPOnboard(config)
    ccp_onboard(mpt_client_mock, context, next_step_mock)
    assert mocked_onboard_status.call_count == 1
    next_step_mock.assert_not_called()


def test_check_onboard_ccp_status_fail(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    ccp_client,
    onboard_customer_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CCP_ONBOARD, ccp_engagement_id="123123"
        )
    )
    mocked_onboard_status = mocker.patch(
        "swo_ccp_client.client.CCPClient.get_onboard_status",
        return_value=onboard_customer_status_factory(CCPOnboardStatusEnum.FAILED),
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    service_client = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.steps.ccp_onboard.get_service_client",
        return_value=service_client,
    )
    mocked_send_error = mocker.patch("swo_aws_extension.flows.steps.ccp_onboard.send_error")

    service_client.create_service_request.return_value = {"id": "1234-5678"}

    ccp_onboard = CCPOnboard(config)
    ccp_onboard(mpt_client_mock, context, next_step_mock)
    assert mocked_onboard_status.call_count == 1
    assert service_client.create_service_request.call_count == 1
    assert mocked_send_error.call_count == 1
    next_step_mock.assert_called_once()


def test_check_onboard_ccp_status_succeeded(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    ccp_client,
    onboard_customer_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CCP_ONBOARD, ccp_engagement_id="123123"
        )
    )
    mocked_onboard_status = mocker.patch(
        "swo_ccp_client.client.CCPClient.get_onboard_status",
        return_value=onboard_customer_status_factory(CCPOnboardStatusEnum.SUCCEEDED),
    )

    updated_order = set_phase(order, PhasesEnum.COMPLETED)
    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.ccp_onboard.update_order",
        return_value=updated_order,
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    ccp_onboard = CCPOnboard(config)
    ccp_onboard(mpt_client_mock, context, next_step_mock)
    assert mocked_onboard_status.call_count == 1
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )
    next_step_mock.assert_called_once()


def test_check_onboard_ccp_http_error(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    ccp_client,
    onboard_customer_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CCP_ONBOARD, ccp_engagement_id="123123"
        )
    )
    mocked_onboard_status = mocker.patch(
        "swo_ccp_client.client.CCPClient.get_onboard_status",
        side_effect=HTTPError(
            response=mocker.Mock(
                status_code=500,
                json=mocker.Mock(side_effect=JSONDecodeError("msg", "doc", 0)),
                content=b"Internal Server Error",
            )
        ),
    )
    mocked_send_error = mocker.patch("swo_aws_extension.flows.steps.ccp_onboard.send_error")
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    ccp_onboard = CCPOnboard(config)
    ccp_onboard(mpt_client_mock, context, next_step_mock)
    assert mocked_onboard_status.call_count == 1
    assert mocked_send_error.call_count == 1
    next_step_mock.assert_not_called()


def test_ccp_onboard_phase_not_ccp_onboard(mocker, order_factory, config, aws_client_factory):
    order = order_factory()

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")

    context = PurchaseContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    ccp_onboard = CCPOnboard(config)
    ccp_onboard(mpt_client_mock, context, next_step_mock)

    mock_client.get_caller_identity.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
