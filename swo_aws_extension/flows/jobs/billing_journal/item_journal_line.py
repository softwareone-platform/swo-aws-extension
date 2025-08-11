import logging
from abc import ABC, abstractmethod

from swo_aws_extension.constants import (
    EXCLUDE_USAGE_SERVICES,
    AWSServiceEnum,
    ItemSkusEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingException
from swo_aws_extension.flows.jobs.billing_journal.models import (
    Description,
    ExternalIds,
    JournalLine,
    Period,
    Price,
    Search,
    SearchItem,
    SearchSubscription,
)

logger = logging.getLogger(__name__)


def get_journal_processors(config):
    """
    Returns a dictionary of journal line processors based on the provided configuration.
    Args:
        config (Config): Configuration object containing billing discount rates.
    Returns:
        dict: A dictionary mapping ItemSkusEnum to corresponding journal line processors.
    """
    tolerance = config.billing_discount_tolerance_rate
    return {
        ItemSkusEnum.AWS_MARKETPLACE.value: GenerateMarketplaceJournalLines(
            UsageMetricTypeEnum.MARKETPLACE.value,
            tolerance,
        ),
        ItemSkusEnum.AWS_USAGE.value: GenerateJournalLines(
            UsageMetricTypeEnum.USAGE.value, tolerance, config.billing_discount_base
        ),
        ItemSkusEnum.AWS_USAGE_INCENTIVATE.value: GenerateJournalLines(
            UsageMetricTypeEnum.USAGE.value, tolerance, config.billing_discount_incentivate
        ),
        ItemSkusEnum.AWS_OTHER_SERVICES.value: GenerateOtherServicesJournalLines(
            UsageMetricTypeEnum.USAGE.value, tolerance, 0
        ),
        ItemSkusEnum.AWS_SUPPORT.value: GenerateSupportJournalLines(
            UsageMetricTypeEnum.SUPPORT.value, tolerance, config.billing_discount_base
        ),
        ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value: GenerateSupportEnterpriseJournalLines(
            UsageMetricTypeEnum.SUPPORT.value, tolerance, config.billing_discount_support_enterprise
        ),
        ItemSkusEnum.SAVING_PLANS_RECURRING_FEE.value: GenerateSavingPlansJournalLines(
            UsageMetricTypeEnum.SAVING_PLANS.value, tolerance, config.billing_discount_base
        ),
        ItemSkusEnum.SAVING_PLANS_RECURRING_FEE_INCENTIVATE.value: GenerateSavingPlansJournalLines(
            UsageMetricTypeEnum.SAVING_PLANS.value, tolerance, config.billing_discount_incentivate
        ),
        ItemSkusEnum.UPFRONT.value: GenerateJournalLines(
            UsageMetricTypeEnum.RECURRING.value, tolerance, config.billing_discount_base
        ),
        ItemSkusEnum.UPFRONT_INCENTIVATE.value: GenerateJournalLines(
            UsageMetricTypeEnum.RECURRING.value, tolerance, config.billing_discount_incentivate
        ),
    }


def create_journal_line(
    service_name,
    amount,
    item_external_id,
    account_id,
    journal_details,
    invoice_id,
    invoice_entity,
    quantity=1,
    segment="COM",
    error=None,
):
    """
    Create a new journal line dictionary for billing purposes.

        Args:
            service_name (str): Name of the AWS service.
            amount (float): Amount to bill.
            item_external_id (str): External item ID.
            account_id (str): AWS account ID.
            journal_details (dict): Journal metadata.
            invoice_id (str): Invoice ID.
            invoice_entity (str): Invoice entity.
            quantity (int, optional): Quantity of the item. Defaults to 1.
            segment (str, optional): Segment for the journal line. Defaults to "COM".
            error (str, optional): Error message if any. Defaults to None.
        Returns:
            dict: Journal line dictionary.
    """
    return JournalLine(
        description=Description(
            value1=service_name,
            value2=f"{account_id}/{invoice_entity}",
        ),
        externalIds=ExternalIds(
            invoice=invoice_id,
            reference=journal_details["agreement_id"],
            vendor=journal_details["mpa_id"],
        ),
        period=Period(
            start=journal_details["start_date"],
            end=journal_details["end_date"],
        ),
        price=Price(
            PPx1=amount,
            unitPP=amount,
        ),
        quantity=quantity,
        search=Search(
            item=SearchItem(
                criteria="item.externalIds.vendor",
                value=item_external_id,
            ),
            subscription=SearchSubscription(
                criteria="subscription.externalIds.vendor",
                value=account_id,
            ),
        ),
        segment=segment,
        error=error,
    )


class GenerateItemJournalLines(ABC):
    """
    Base class for generating journal lines for different AWS billing items.
    """

    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=0):
        self.metric_id = metric_id
        self.billing_discount_tolerance_rate = billing_discount_tolerance_rate
        self.discount = discount

    @abstractmethod
    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        raise NotImplementedError

    @staticmethod
    def _get_support_discount(support_metrics, discount):
        """
        Calculates the support discount based on the refund and support amounts from the
        per record cost metric.
        Args:
            support_metrics (dict): Support metrics from the AWS report.
            discount (float): Discount amount from the AWS report.
        Returns:
            int: Support discount percentage rounded to the nearest integer.
        """
        if len(support_metrics) > 1:
            error_message = (
                f"Multiple support metrics found: {support_metrics} with discount {discount}. "
            )
            logger.error(error_message)
            error_payload = {
                "service_name": AWSServiceEnum.SUPPORT.value,
                "amount": 0,
            }
            raise AWSBillingException(error_message, error_payload)

        support = next(iter(support_metrics.values()), 0)
        support_discount = discount / support * 100 if support != 0 else 0
        return round(abs(support_discount))

    def _get_usage_journal_lines(
        self,
        metric_id,
        account_metrics,
        account_invoices,
        item_external_id,
        account_id,
        journal_details,
        target_discount=None,
        skip_services=None,
    ):
        """
        Generates journal lines for a specific usage metric, filtering by target discount and
        skipping specified services.
        Args:
            metric_id (str): Metric identifier (e.g., MARKETPLACE, USAGE).
            account_metrics (dict): Metrics for the account.
            account_invoices (dict): Invoices for the account.
            item_external_id (str): External item ID.
            account_id (str): AWS account ID.
            journal_details (dict): Journal metadata.
            target_discount (float, optional): Target discount percentage to filter journal lines.
            skip_services (list, optional): List of services to skip in the journal lines.
        Returns:
            list: List of journal line dictionaries for the specified metric.
        """
        journal_lines = []
        metric_dict = account_metrics.get(metric_id, {})
        skip_services = skip_services if skip_services else []
        usage = account_metrics.get(UsageMetricTypeEnum.USAGE.value, {})
        recurring = account_metrics.get(UsageMetricTypeEnum.RECURRING.value, {})
        partner_discount = account_metrics.get(UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {})

        filtered_metrics = {s: a for s, a in metric_dict.items() if s not in skip_services}
        for service_name, amount in filtered_metrics.items():
            if target_discount is not None:
                if metric_id in [
                    UsageMetricTypeEnum.USAGE,
                    UsageMetricTypeEnum.RECURRING,
                ]:
                    total_service_amount = usage.get(service_name, 0.0) + recurring.get(
                        service_name, 0.0
                    )
                else:
                    total_service_amount = amount

                if not self._is_service_discount_valid(
                    total_service_amount,
                    partner_discount.get(service_name, 0),
                    target_discount,
                ):
                    continue
            invoice_entity = account_metrics.get(
                UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value, {}
            ).get(service_name, "")
            invoice_id = account_invoices.get(invoice_entity, {}).get("invoice_id", "")
            journal_lines.append(
                create_journal_line(
                    service_name,
                    amount,
                    item_external_id,
                    account_id,
                    journal_details,
                    invoice_id,
                    invoice_entity,
                )
            )
        return journal_lines

    def _is_service_discount_valid(self, amount, discount, target_discount):
        """
        Validates if the service discount is within the acceptable range based on
        the target discount.
        Args:
            amount (float): The total amount for the service.
            discount (float): The discount provided by the partner.
            target_discount (float): The target discount percentage to validate against.
        Returns:
            bool: True if the discount is valid, False otherwise.
        """
        partner_amount = amount - abs(discount)
        discount = ((amount - partner_amount) / amount) * 100 if amount != 0 else 0
        if target_discount == 0 and discount != 0:
            return False
        if abs(discount - target_discount) > self.billing_discount_tolerance_rate:
            return False
        return True


class GenerateMarketplaceJournalLines(GenerateItemJournalLines):
    """
    Generate journal lines for AWS Marketplace usage metrics.
    """

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        return self._get_usage_journal_lines(
            UsageMetricTypeEnum.MARKETPLACE,
            account_metrics,
            account_invoices,
            item_external_id,
            account_id,
            journal_details,
            skip_services=[AWSServiceEnum.TAX],
        )


class GenerateJournalLines(GenerateItemJournalLines):
    """
    Generate journal lines for AWS usage metrics
    """

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        return self._get_usage_journal_lines(
            self.metric_id,
            account_metrics,
            account_invoices,
            item_external_id,
            account_id,
            journal_details,
            target_discount=self.discount,
            skip_services=EXCLUDE_USAGE_SERVICES,
        )


class GenerateSavingPlansJournalLines(GenerateItemJournalLines):
    """
    Generate journal lines for AWS usage metrics
    """

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        return self._get_usage_journal_lines(
            self.metric_id,
            account_metrics,
            account_invoices,
            item_external_id,
            account_id,
            journal_details,
            target_discount=self.discount,
        )


class GenerateOtherServicesJournalLines(GenerateItemJournalLines):
    """
    Generate journal lines for other AWS services excluding usage and marketplace services.
    """

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        exclude_services = []
        exclude_services.extend(EXCLUDE_USAGE_SERVICES)
        exclude_services.append(AWSServiceEnum.TAX)
        exclude_services.append(AWSServiceEnum.REFUND)
        marketplace_services = account_metrics.get(UsageMetricTypeEnum.MARKETPLACE.value, {}).keys()

        exclude_services.extend(marketplace_services)
        support_services = account_metrics.get(UsageMetricTypeEnum.SUPPORT.value, {}).keys()
        exclude_services.extend(support_services)
        return self._get_usage_journal_lines(
            self.metric_id,
            account_metrics,
            account_invoices,
            item_external_id,
            account_id,
            journal_details,
            target_discount=self.discount,
            skip_services=exclude_services,
        )


class GenerateSupportJournalLines(GenerateItemJournalLines):
    """
    Generate journal lines for AWS support usage metrics.
    """

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        refund_metrics = account_metrics.get(UsageMetricTypeEnum.REFUND.value, {})
        discount = next(iter(refund_metrics.values()), 0)
        support_discount = self._get_support_discount(
            account_metrics.get(UsageMetricTypeEnum.SUPPORT.value, {}), discount
        )
        if support_discount == self.discount:
            return self._get_usage_journal_lines(
                self.metric_id,
                account_metrics,
                account_invoices,
                item_external_id,
                account_id,
                journal_details,
            )
        return []


class GenerateSupportEnterpriseJournalLines(GenerateItemJournalLines):
    """
    Generate journal lines for AWS support enterprise usage metrics.
    """

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        support_metrics = account_metrics.get(UsageMetricTypeEnum.SUPPORT.value, {})
        provider_discount_metrics = account_metrics.get(
            UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {}
        )
        support_name = next(iter(support_metrics.keys()), 0)
        discount = abs(provider_discount_metrics.get(support_name, 0))
        support_discount = self._get_support_discount(support_metrics, discount)

        if support_discount == self.discount:
            return self._get_usage_journal_lines(
                self.metric_id,
                account_metrics,
                account_invoices,
                item_external_id,
                account_id,
                journal_details,
            )
        return []
