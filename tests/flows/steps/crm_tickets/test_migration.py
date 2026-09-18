import pytest

from swo_aws_extension.constants import ChannelHandshakeDeployed, PhasesEnum, SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.migration import CRMTicketMigration
from swo_aws_extension.flows.steps.crm_tickets.templates.migration import MIGRATION_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_crm_migration_ticket_id
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


@pytest.fixture
def migration_context(order_factory, order_parameters_factory, fulfillment_parameters_factory):
    def factory(phase=PhasesEnum.CREATE_SUBSCRIPTION.value, ticket_id=""):
        order = order_factory(
            order_parameters=order_parameters_factory(
                support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
            ),
            fulfillment_parameters=fulfillment_parameters_factory(
                phase=phase,
                cco_contract_number="CCO-1",
                channel_handshake_approved=ChannelHandshakeDeployed.YES.value,
                crm_migration_ticket_id=ticket_id,
            ),
        )
        return PurchaseContext.from_order_data(order)

    return factory


def test_pre_step_skips_wrong_phase(migration_context, config):
    context = migration_context(phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value)

    with pytest.raises(SkipStepError):
        CRMTicketMigration(config).pre_step(context)


def test_pre_step_skips_ticket_exists(migration_context, config):
    context = migration_context(ticket_id="TICKET-123")

    with pytest.raises(SkipStepError):
        CRMTicketMigration(config).pre_step(context)


def test_pre_step_proceeds_conditions_met(migration_context, config):
    context = migration_context()

    CRMTicketMigration(config).pre_step(context)  # act

    assert context.order is not None


def test_process_creates_service_request(migration_context, mpt_client, mock_crm_client, config):
    context = migration_context()
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketMigration(config).process(mpt_client, context)  # act

    expected_service_request = ServiceRequest(
        additional_info=MIGRATION_TEMPLATE.additional_info,
        summary=MIGRATION_TEMPLATE.summary.format(
            customer_name="A buyer",
            buyer_id="BUY-1111-1111",
            buyer_external_id="",
            seller_country="US",
            pm_account_id="123456789012",
            order_id=context.order_id,
            agreement_id="AGR-2119-4550-8674-5962",
            master_payer_id="651706759263",
            cco_contract_number="CCO-1",
            handshake_approved="Yes",
            technical_contact_name="John Doe",
            technical_contact_email="john.doe@example.com",
            technical_contact_phone="+34600111222",
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
        ),
        title=MIGRATION_TEMPLATE.title,
    )
    mock_crm_client.return_value.create_service_request.assert_called_once_with(
        context.order_id, expected_service_request
    )
    assert get_crm_migration_ticket_id(context.order) == "TICKET-123"


def test_process_logs_ticket_creation(
    migration_context, mpt_client, mock_crm_client, config, caplog
):
    context = migration_context()
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketMigration(config).process(mpt_client, context)  # act

    assert "Migration ticket created with ID TICKET-123" in caplog.text


def test_process_raises_error_when_crm_fails(
    migration_context, mpt_client, mock_crm_client, config
):
    context = migration_context()
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")

    with pytest.raises(UnexpectedStopError) as error:
        CRMTicketMigration(config).process(mpt_client, context)

    assert error.value.title == "Error creating Migration ticket"


def test_post_step_updates_order_parameters(mocker, migration_context, mpt_client, config):
    context = migration_context(ticket_id="TICKET-123")
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.base.update_order",
        return_value=context.order,
    )

    CRMTicketMigration(config).post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
