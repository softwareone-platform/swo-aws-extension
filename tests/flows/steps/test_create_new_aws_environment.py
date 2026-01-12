import pytest

from swo_aws_extension.constants import (
    CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
    CRM_NEW_ACCOUNT_SUMMARY,
    CRM_NEW_ACCOUNT_TITLE,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.create_new_aws_environment import CreateNewAWSEnvironment
from swo_aws_extension.flows.steps.errors import (
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_crm_new_account_ticket_id,
    get_mpa_account_id,
    get_phase,
)
from swo_aws_extension.swo.crm_service.client import CRMServiceClient, ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


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


def test_process_creates_ticket_when_missing(
    mocker,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
        order_parameters=order_parameters_factory(mpa_id=""),
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client = mocker.MagicMock()
    mock_crm_client.create_service_request.return_value = {"id": "TICKET-123"}
    mocker.patch(
        "swo_aws_extension.flows.steps.create_new_aws_environment.get_service_client",
        return_value=mock_crm_client,
    )

    with pytest.raises(QueryStepError) as error:
        CreateNewAWSEnvironment(config).process(mpt_client, context)

    assert error.value.template_id == OrderQueryingTemplateEnum.NEW_ACCOUNT_CREATION.value
    expected_service_request = ServiceRequest(
        additional_info=CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
        summary=CRM_NEW_ACCOUNT_SUMMARY.format(
            customer_name=context.buyer.get("name"),
            buyer_external_id=context.buyer.get("id"),
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
        ),
        title=CRM_NEW_ACCOUNT_TITLE,
    )
    mock_crm_client.create_service_request.assert_called_once_with(
        context.order_id, expected_service_request
    )
    assert get_crm_new_account_ticket_id(context.order) == "TICKET-123"


def test_process_raises_query_error_mpa_missing(
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
            crm_new_account_ticket_id="TICKET-123",
        ),
        order_parameters=order_parameters_factory(mpa_id=""),
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer

    with pytest.raises(QueryStepError) as error:
        CreateNewAWSEnvironment(config).process(mpt_client, context)

    assert error.value.template_id == OrderQueryingTemplateEnum.NEW_ACCOUNT_CREATION.value


def test_process_succeeds_when_mpa_exists(
    mocker,
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
            crm_new_account_ticket_id="TICKET-123",
        ),
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
    )
    context = PurchaseContext.from_order_data(order)

    CreateNewAWSEnvironment(config).process(mpt_client, context)  # act

    assert (
        "ORD-0792-5000-2253-4210 - Next - Create New AWS Environment completed successfully"
        in caplog.text
    )


def test_process_raises_error_when_crm_fails(
    mocker,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        ),
        order_parameters=order_parameters_factory(mpa_id=""),
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client = mocker.MagicMock(spec=CRMServiceClient)
    mock_crm_client.create_service_request.side_effect = CRMError("CRM API error")
    mocker.patch(
        "swo_aws_extension.flows.steps.create_new_aws_environment.get_service_client",
        return_value=mock_crm_client,
    )

    with pytest.raises(UnexpectedStopError) as error:
        CreateNewAWSEnvironment(config).process(mpt_client, context)

    assert "Error creating New Account ticket" in error.value.title


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
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.create_new_aws_environment.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value
    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
