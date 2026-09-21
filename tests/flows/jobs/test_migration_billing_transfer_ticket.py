import pytest
from mpt_api_client.exceptions import MPTError

from swo_aws_extension.airtable.models import AccountMigrationRecord, AccountMigrationStatus
from swo_aws_extension.constants import FulfillmentParametersEnum
from swo_aws_extension.flows.jobs.migration_billing_transfer_ticket import (
    build_ticket_request,
    create_ticket,
    get_stored_ticket_id,
    store_ticket_id,
)
from swo_aws_extension.flows.steps.crm_tickets.templates.billing_transfer_start import (
    BILLING_TRANSFER_START_TEMPLATE,
)

MODULE = "swo_aws_extension.flows.jobs.migration_billing_transfer_ticket"
ORDER_ID = "ORD-0792-5000-2253-4210"
AGREEMENT_ID = "AGR-2119-4550-8674-5962"
TICKET_ID = "CS0004728"


@pytest.fixture
def record():
    return AccountMigrationRecord(
        record_id="rec123",
        swo_seller="SEL-1111-1111",
        swo_buyer="BUY-1111-1111",
        masterpayer="123456789012",
        mpt_cco="CCO-0001",
        aws_account_email="root@example.com",
        aws_support_type="resoldSupport",
        technical_contact_name="Jane Doe",
        technical_contact_email="jane.doe@example.com",
        group="Group A",
        batch="Batch 1",
        migration_status=AccountMigrationStatus.COMPLETED,
        mpt_order_id=ORDER_ID,
        billing_transfer_start_date="2026-09-01",
    )


@pytest.fixture
def order(buyer, seller, fulfillment_parameters_factory):
    return {
        "id": ORDER_ID,
        "agreement": {
            "id": AGREEMENT_ID,
            "parameters": {
                "ordering": [],
                "fulfillment": fulfillment_parameters_factory(crm_migration_ticket_id=TICKET_ID),
            },
        },
        "buyer": buyer,
        "seller": seller,
    }


def test_get_stored_ticket_id(order):
    result = get_stored_ticket_id(order)

    assert result == TICKET_ID


@pytest.mark.parametrize("agreement", [None, {"id": AGREEMENT_ID}])
def test_get_stored_ticket_id_without_agreement_parameters(agreement):
    result = get_stored_ticket_id({"id": ORDER_ID, "agreement": agreement})

    assert result is None


def test_build_ticket_request_fills_the_template(record, order, buyer):
    result = build_ticket_request(record, order, "2026-09-01")

    assert (result.title, result.additional_info) == (
        BILLING_TRANSFER_START_TEMPLATE.title,
        BILLING_TRANSFER_START_TEMPLATE.additional_info,
    )
    assert f"<li><b>Customer:</b> {buyer['name']}</li>" in result.summary
    assert f"<li><b>Agreement:</b> {AGREEMENT_ID}</li>" in result.summary
    assert "<li><b>Seller Country:</b> US</li>" in result.summary
    assert "<li><b>Phone:</b> N/A</li>" in result.summary


def test_build_ticket_request_without_buyer_and_seller(record):
    result = build_ticket_request(record, {"id": ORDER_ID, "agreement": None}, "2026-09-01")

    assert "<li><b>Buyer:</b> BUY-1111-1111</li>" in result.summary
    assert "<li><b>Seller Country:</b> </li>" in result.summary
    assert "<li><b>Agreement:</b> </li>" in result.summary


def test_create_ticket_returns_the_ticket_id(mocker, record, order):
    mock_client = mocker.patch(f"{MODULE}.get_service_client").return_value
    mock_client.create_service_request.return_value = {"id": TICKET_ID}

    result = create_ticket(record, order, "2026-09-01")

    assert result == TICKET_ID
    mock_client.create_service_request.assert_called_once_with(
        ORDER_ID, build_ticket_request(record, order, "2026-09-01")
    )


def test_store_ticket_id_updates_the_agreement(mocker, mpt_client, order):
    mock_update_agreement = mocker.patch(f"{MODULE}.update_agreement")

    result = store_ticket_id(mpt_client, order, TICKET_ID)

    assert result is True
    mock_update_agreement.assert_called_once_with(
        mpt_client,
        AGREEMENT_ID,
        parameters={
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.CRM_MIGRATION_TICKET_ID.value,
                    "value": TICKET_ID,
                }
            ]
        },
    )


def test_store_ticket_id_reports_marketplace_error(mocker, mpt_client, order):
    mocker.patch(f"{MODULE}.update_agreement", side_effect=MPTError("error"))

    result = store_ticket_id(mpt_client, order, TICKET_ID)

    assert result is False
