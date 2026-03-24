from decimal import Decimal

import pytest

from swo_aws_extension.constants import (
    AWSRecordTypeEnum,
    ChannelHandshakeDeployed,
    SupportTypesEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.discount.extra_discounts import (
    ExtraDiscountsManager,
    PlSDiscountProcessor,
    ServiceDiscountProcessor,
    SupportDiscountProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)


def create_metric(service_name, record_type, amount, invoice_entity="Entity1"):
    return ServiceMetric(
        service_name=service_name,
        record_type=record_type,
        amount=Decimal(amount),
        invoice_entity=invoice_entity,
        invoice_id="INV-123",
    )


def build_usage_result(metrics_by_account):
    return OrganizationUsageResult(
        reports=OrganizationReport(),
        usage_by_account={
            account_id: AccountUsage(metrics=metrics)
            for account_id, metrics in metrics_by_account.items()
        },
    )


@pytest.fixture
def agreement():
    return {
        "parameters": {
            "ordering": [],
            "fulfillment": [
                {
                    "externalId": "channelHandshakeApproved",
                    "value": ChannelHandshakeDeployed.YES,
                }
            ],
        }
    }


@pytest.fixture
def organization_invoice():
    return OrganizationInvoice(
        principal_invoice_amount=Decimal("100.0"),
        entities={
            "Entity1": InvoiceEntity(
                invoice_id="INV-123",
                base_currency_code="USD",
                payment_currency_code="USD",
                exchange_rate=Decimal("1.0"),
            )
        },
    )


@pytest.fixture
def journal_details():
    return JournalDetails(
        agreement_id="AGR-1",
        mpa_id="MPA-1",
        start_date="2023-11-01",
        end_date="2023-11-30",
    )


@pytest.fixture
def usage_result():
    return build_usage_result({"ACC-1": []})


def test_service_discount_processor(
    agreement,
    usage_result,
    journal_details,
    organization_invoice,
):
    agreement["parameters"]["fulfillment"].append(
        {"externalId": "serviceDiscount", "value": "5.0"},
    )
    usage_result.usage_by_account["ACC-1"].metrics.extend([
        create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00"),
        create_metric("EC2", AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT, "-10.00"),
        create_metric("RDS", AWSRecordTypeEnum.RECURRING, "50.00"),
        create_metric("RDS", AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT, "-5.00"),
        create_metric("Marketplace", "Marketplace", "20.00"),
        create_metric("Marketplace", AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT, "-2.00"),
    ])
    processor = ServiceDiscountProcessor()

    lines = processor.process(  # act
        agreement, usage_result, journal_details, organization_invoice
    )

    assert len(lines) == 1
    assert lines[0].price.unit_pp == Decimal("-0.75")
    assert lines[0].description.value1 == "SWO additional Usage discount"
    assert lines[0].external_ids.vendor == "MPA-1"


@pytest.mark.parametrize(
    ("processor_factory", "discount_param", "support_type"),
    [
        (ServiceDiscountProcessor, "serviceDiscount", None),
        (SupportDiscountProcessor, "supportDiscount", SupportTypesEnum.AWS_RESOLD_SUPPORT),
        (
            lambda: PlSDiscountProcessor(Decimal("5.0")),
            "plsDiscount",
            SupportTypesEnum.PARTNER_LED_SUPPORT,
        ),
    ],
)
def test_returns_empty_when_handshake_not_approved(
    agreement,
    usage_result,
    journal_details,
    organization_invoice,
    processor_factory,
    discount_param,
    support_type,
):
    agreement["parameters"]["fulfillment"] = [
        {"externalId": "channelHandshakeApproved", "value": ChannelHandshakeDeployed.NO_DEPLOYED},
        {"externalId": discount_param, "value": "5.0"},
    ]
    if support_type:
        agreement["parameters"]["ordering"].append(
            {"externalId": "supportType", "value": support_type},
        )
    processor = processor_factory()

    lines = processor.process(  # act
        agreement, usage_result, journal_details, organization_invoice
    )

    assert len(lines) == 0


def test_extra_discounts_manager(
    agreement,
    usage_result,
    journal_details,
    organization_invoice,
):
    agreement["parameters"]["fulfillment"].extend([
        {"externalId": "serviceDiscount", "value": "5.0"},
        {"externalId": "supportDiscount", "value": "20.0"},
    ])
    agreement["parameters"]["ordering"].append({
        "externalId": "supportType",
        "value": SupportTypesEnum.AWS_RESOLD_SUPPORT,
    })
    usage_result.usage_by_account["ACC-1"].metrics.extend([
        create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00"),
        create_metric("EC2", AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT, "-10.00"),
    ])
    usage_result.usage_by_account["ACC-2"] = AccountUsage(
        metrics=[
            create_metric("Support", AWSRecordTypeEnum.SUPPORT, "50.00"),
            create_metric("Support", AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT, "-5.00"),
        ]
    )
    manager = ExtraDiscountsManager(Decimal("5.0"))

    lines = manager.process(  # act
        agreement, usage_result, journal_details, organization_invoice
    )

    assert len(lines) == 2
    service_line = next(
        line for line in lines if line.description.value1 == "SWO additional Usage discount"
    )
    assert service_line.price.unit_pp == Decimal("-0.50")
    support_line = next(
        line for line in lines if line.description.value1 == "SWO additional Support discount"
    )
    assert support_line.price.unit_pp == Decimal("-1.00")


def test_returns_empty_when_discount_percentage_is_zero(
    agreement,
    usage_result,
    journal_details,
    organization_invoice,
):
    agreement["parameters"]["fulfillment"].append(
        {"externalId": "serviceDiscount", "value": "0"},
    )
    usage_result.usage_by_account["ACC-1"].metrics.extend([
        create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00"),
        create_metric("EC2", AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT, "-10.00"),
    ])
    processor = ServiceDiscountProcessor()

    result = processor.process(agreement, usage_result, journal_details, organization_invoice)

    assert len(result) == 0


def test_returns_empty_when_base_amount_is_zero(
    agreement,
    usage_result,
    journal_details,
    organization_invoice,
):
    agreement["parameters"]["fulfillment"].append(
        {"externalId": "serviceDiscount", "value": "5.0"},
    )
    processor = ServiceDiscountProcessor()

    result = processor.process(agreement, usage_result, journal_details, organization_invoice)

    assert len(result) == 0


@pytest.mark.parametrize(
    ("invoice_entity", "base_currency", "payment_currency", "exchange_rate", "expected_amount"),
    [
        ("AWS EMEA", "USD", "EUR", "0.90", Decimal("-0.9")),
        ("AWS Inc.", "USD", "USD", "1.0", Decimal("-1.0")),
        ("AWS Inc.", "USD", "EUR", "0", Decimal("-1.0")),
        ("Unknown", "USD", "USD", "1.0", Decimal("-1.0")),
    ],
    ids=[
        "applies_exchange_rate",
        "same_currency_no_conversion",
        "zero_rate_no_conversion",
        "entity_not_found_no_conversion",
    ],
)
def test_resolve_service_amount_with_exchange_rate_rules(
    agreement,
    journal_details,
    invoice_entity,
    base_currency,
    payment_currency,
    exchange_rate,
    expected_amount,
):
    entity_name = "AWS Inc." if invoice_entity == "Unknown" else invoice_entity
    invoice = OrganizationInvoice(
        principal_invoice_amount=Decimal("100.0"),
        entities={
            entity_name: InvoiceEntity(
                invoice_id="INV-001",
                base_currency_code=base_currency,
                payment_currency_code=payment_currency,
                exchange_rate=Decimal(exchange_rate),
            )
        },
    )
    usage_result = build_usage_result({
        "ACC-1": [
            create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00", invoice_entity),
            create_metric(
                "EC2",
                AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
                "-10.00",
                invoice_entity,
            ),
        ],
    })
    agreement["parameters"]["fulfillment"].append(
        {"externalId": "serviceDiscount", "value": "10.0"},
    )
    processor = ServiceDiscountProcessor()

    result = processor.process(agreement, usage_result, journal_details, invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == expected_amount


def test_pls_discount_processor(
    agreement,
    usage_result,
    journal_details,
    organization_invoice,
):
    agreement["parameters"]["ordering"].append(
        {"externalId": "supportType", "value": SupportTypesEnum.PARTNER_LED_SUPPORT},
    )
    agreement["parameters"]["fulfillment"].append(
        {"externalId": "plsDiscount", "value": "20.0"},
    )
    usage_result.usage_by_account["ACC-1"].metrics.extend([
        create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00"),
        create_metric("RDS", AWSRecordTypeEnum.USAGE, "50.00"),
    ])
    processor = PlSDiscountProcessor(Decimal("5.0"))

    result = processor.process(agreement, usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("30.000000")
    assert result[0].description.value1 == "SWO additional PLS Support discount"
    assert result[0].external_ids.vendor == "MPA-1"


@pytest.mark.parametrize(
    "principal_amount",
    [None, Decimal(0)],
    ids=["none", "zero"],
)
def test_extra_discounts_manager_skips_when_principal_amount_is_zero_or_none(
    agreement,
    usage_result,
    journal_details,
    principal_amount,
):
    invoice = OrganizationInvoice(principal_invoice_amount=principal_amount)
    manager = ExtraDiscountsManager(Decimal("5.0"))

    result = manager.process(agreement, usage_result, journal_details, invoice)

    assert not result
