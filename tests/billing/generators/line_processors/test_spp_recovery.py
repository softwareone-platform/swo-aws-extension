from decimal import Decimal

import pytest

from swo_aws_extension.billing.generators.line_processors.spp_recovery import (
    SPP_PREFIX,
    SPP_SUFFIX,
    SppRecoveryJournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails
from swo_aws_extension.billing.models.usage import AccountUsage, ServiceMetric
from swo_aws_extension.constants import AWSRecordTypeEnum, ItemSkuEnum


@pytest.fixture
def journal_details():
    return JournalDetails(
        agreement_id="AGR-123",
        mpa_id="MPA-456",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )


@pytest.fixture
def spp_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        amount=Decimal("-5.00"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )


def build_context(journal_details, metrics, principal_invoice_amount=None):
    return LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=metrics),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(
            principal_invoice_amount=principal_invoice_amount,
        ),
    )


@pytest.mark.parametrize(
    "principal_invoice_amount",
    [Decimal("100.00"), Decimal("-50.00"), None],
)
def test_process_skips_spp_when_principal_invoice_not_zero(
    journal_details, spp_metric, principal_invoice_amount
):
    context = build_context(journal_details, [spp_metric], principal_invoice_amount)

    result = SppRecoveryJournalLineProcessor().process(spp_metric, context)

    assert result == []


def test_process_returns_spp_when_principal_invoice_zero(journal_details, spp_metric):
    context = build_context(journal_details, [spp_metric], Decimal(0))

    result = SppRecoveryJournalLineProcessor().process(spp_metric, context)

    assert len(result) == 1
    assert result[0].description.value1 == f"{SPP_PREFIX}Amazon S3{SPP_SUFFIX}"
    assert result[0].price.pp_x1 == Decimal("-5.00")
    assert result[0].search.search_item.criteria_value == ItemSkuEnum.ADDITIONAL_CHARGES_SKU
