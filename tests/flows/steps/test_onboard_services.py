import pytest

from swo_aws_extension.constants import (
    CRM_ONBOARD_ADDITIONAL_INFO,
    CRM_ONBOARD_SUMMARY,
    CRM_ONBOARD_TITLE,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.errors import AlreadyProcessedStepError, SkipStepError
from swo_aws_extension.flows.steps.onboard_services import OnboardServices
from swo_aws_extension.parameters import (
    get_cost_management,
    get_crm_onboard_ticket_id,
    get_mpa_account_id,
    get_phase,
    get_resold_support_plans,
    get_supplementary_services,
    get_support_type,
    get_technical_contact_info,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


@pytest.fixture
def mock_crm_client(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.onboard_services.get_service_client")


@pytest.fixture
def purchase_context(order_factory):
    def factory(order=None):
        if order is None:
            order = order_factory()
        return PurchaseContext.from_order_data(order)

    return factory


def test_pre_step_skips_wrong_phase(
    order_factory, fulfillment_parameters_factory, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )
    context = purchase_context(order)
    step = OnboardServices(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_pre_step_already_processed(
    order_factory, fulfillment_parameters_factory, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
            crm_onboard_ticket_id="CS0004728",
        )
    )
    context = purchase_context(order)
    step = OnboardServices(config)

    with pytest.raises(AlreadyProcessedStepError):
        step.pre_step(context)

    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTION.value


def test_pre_step_proceeds(order_factory, fulfillment_parameters_factory, purchase_context, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
            crm_onboard_ticket_id="",
        )
    )
    context = purchase_context(order)
    step = OnboardServices(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_creates_service_request(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    purchase_context,
    config,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    context = purchase_context(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "CS0004728"}
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    expected_service_request = ServiceRequest(
        additional_info=CRM_ONBOARD_ADDITIONAL_INFO,
        summary=CRM_ONBOARD_SUMMARY.format(
            customer_name=context.buyer.get("name"),
            buyer_external_id=context.buyer.get("id"),
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact=get_technical_contact_info(context.order),
            support_type=get_support_type(context.order),
            resold_support_plans=get_resold_support_plans(context.order),
            cost_management=get_cost_management(context.order),
            supplementary_services=get_supplementary_services(context.order),
        ),
        title=CRM_ONBOARD_TITLE,
    )
    mock_crm_client.return_value.create_service_request.assert_called_once_with(
        context.order_id, expected_service_request
    )


def test_process_sets_ticket_id(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    purchase_context,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    context = purchase_context(order)
    mock_crm_client.return_value.create_service_request.return_value = {"id": "CS0004728"}
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    assert get_crm_onboard_ticket_id(context.order) == "CS0004728"


def test_process_logs_ticket_creation(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    caplog,
    purchase_context,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    context = purchase_context(order)
    mock_crm_client.return_value.create_service_request.return_value = {"id": "CS0004728"}
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    assert "Onboard services ticket created with ID CS0004728" in caplog.text


def test_process_logs_when_no_ticket_id(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    caplog,
    purchase_context,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    context = purchase_context(order)
    mock_crm_client.return_value.create_service_request.return_value = {"status": "created"}
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    assert "No ticket ID returned from CRM" in caplog.text
    assert not get_crm_onboard_ticket_id(context.order)


def test_process_handles_crm_error(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    caplog,
    purchase_context,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    context = purchase_context(order)
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    assert "Failed to create onboard services ticket: CRMError: CRM API error" in caplog.text


def test_post_step_sets_create_subscription_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    context = purchase_context(order)
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.onboard_services.update_order",
        return_value=updated_order,
    )
    step = OnboardServices(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTION.value
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][0] == mpt_client
    assert call_args[0][1] == context.order_id
    assert call_args[1]["parameters"] is not None
