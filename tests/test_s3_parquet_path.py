from swo_aws_extension.flows.jobs.billing_journal.generators.cost_usage_report import (
    CostUsageReportGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod


def test_s3_parquet_path(mocker):
    # Create instance without calling __init__
    aws_client = mocker.MagicMock()
    aws_client.account_id = "651706759263"
    generator = CostUsageReportGenerator(aws_client)

    mocker.patch.object(
        generator,
        "_get_billing_view_arn",
        return_value=(
            "arn:aws:billing::651706759263:billingview/"
            "billing-transfer-78023a73-326a-440e-81b8-006c15c7968e"
        ),
    )

    billing_period = BillingPeriod(start_date="2026-03-01", end_date="2026-03-31")
    result = generator.s3_parquet_path("123456789012", billing_period)

    assert (
        result
        == "cur-651706759263/billing-transfer-78023a73-326a-440e-81b8-006c15c7968e/651706759263-123456789012-78023a73-326a-440e-81b8-006c15c7968e/data/BILLING_PERIOD=2026-03"
        # cur-651706759263/billing-transfer-41fb5b71-e417-4d08-92c4-b25030ed36af/651706759263-225989344502-41fb5b71-e417-4d08-92c4-b25030ed36af/data/BILLING_PERIOD=2026-03/651706759263-225989344502-41fb5b71-e417-4d08-92c4-b25030ed36af-00001.snappy.parquet
    )
