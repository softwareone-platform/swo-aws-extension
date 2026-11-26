import pytest

from swo_aws_extension.billing.generators.billable_agreements_query import (
    BillableAgreementsQuery,
)
from swo_aws_extension.models import BillingPeriod


@pytest.mark.parametrize(
    ("billing_period", "expected_window_start"),
    [
        (BillingPeriod(start_date="2025-10-01", end_date="2025-11-01"), "2025-04-01"),
        (BillingPeriod(start_date="2026-03-01", end_date="2026-04-01"), "2025-09-01"),
        (BillingPeriod(start_date="2026-06-01", end_date="2026-07-01"), "2025-12-01"),
    ],
)
def test_build(billing_period, expected_window_start):
    query = BillableAgreementsQuery(
        authorization_id="AUTH-1",
        product_ids=["PROD-1"],
        billing_period=billing_period,
    )

    result = query.build()

    assert str(result) == (
        "and(eq(authorization.id,'AUTH-1'),"
        "or(in(status,(Active,Updating)),"
        "and(eq(status,'Terminated'),"
        "any(parameters.fulfillment,and(eq(externalId,'relationshipEndDate'),"
        f"ge(displayValue,'{expected_window_start}'))))),"
        "in(product.id,(PROD-1)))"
    )
