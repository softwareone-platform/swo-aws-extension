from dataclasses import dataclass

from dateutil.relativedelta import relativedelta

from swo_aws_extension.constants import (
    TERMINATED_AGREEMENT_BILLING_WINDOW_MONTHS,
    AgreementStatusEnum,
    FulfillmentParametersEnum,
)
from swo_aws_extension.models import BillingPeriod
from swo_aws_extension.swo.rql.query_builder import RQLQuery


@dataclass(frozen=True)
class BillableAgreementsQuery:
    """Builds the RQL query that selects the agreements to bill for a billing period."""

    authorization_id: str
    product_ids: list[str]
    billing_period: BillingPeriod

    def build(self) -> RQLQuery:
        """Return the RQL query for the billable agreements of the authorization."""
        active = RQLQuery(status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING])
        return (
            RQLQuery(authorization__id=self.authorization_id)
            & (active | self._recently_terminated())
            & RQLQuery(product__id__in=self.product_ids)
        )

    def _recently_terminated(self) -> RQLQuery:
        # The API filters parameters on displayValue (filled from value), not on value, and
        # compares it as text.
        end_date_in_window = RQLQuery(
            externalId=FulfillmentParametersEnum.RELATIONSHIP_END_DATE.value,
        ) & RQLQuery(displayValue__ge=self._window_start())
        return RQLQuery(status=AgreementStatusEnum.TERMINATED) & end_date_in_window.any(
            "parameters.fulfillment"
        )

    def _window_start(self) -> str:
        window_start = self.billing_period.start_datetime - relativedelta(
            months=TERMINATED_AGREEMENT_BILLING_WINDOW_MONTHS
        )
        # Date-only bound: the "+" of a UTC offset would not survive the unencoded query string.
        return window_start.date().isoformat()
