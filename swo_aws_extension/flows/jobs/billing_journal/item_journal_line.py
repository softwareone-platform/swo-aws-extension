import logging
from abc import ABC, abstractmethod
from typing import override

from swo_aws_extension.constants import (
    AWSServiceEnum,
    ItemSkusEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingError
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
            UsageMetricTypeEnum.MARKETPLACE.value, tolerance
        ),
        ItemSkusEnum.AWS_USAGE.value: GenerateUsageJournalLines(
            UsageMetricTypeEnum.USAGE.value, tolerance, config.billing_discount_base
        ),
        ItemSkusEnum.AWS_USAGE_INCENTIVATE.value: GenerateUsageJournalLines(
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
        ItemSkusEnum.UPFRONT.value: GenerateUsageJournalLines(
            UsageMetricTypeEnum.RECURRING.value, tolerance, config.billing_discount_base
        ),
        ItemSkusEnum.UPFRONT_INCENTIVATE.value: GenerateUsageJournalLines(
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


class DiscountValidator(ABC):
    """Base class for discount validation."""
    @abstractmethod
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        """Validate discount on AWS."""
        raise NotImplementedError

    def _calculate_provider_discount(self, discount, amount):
        partner_amount = amount - abs(discount)
        return ((amount - partner_amount) / amount) * 100 if amount != 0 else 0

    def _get_support_discount(self, support_metrics, discount):
        if len(support_metrics) > 1:
            error_message = (
                f"Multiple support metrics found: {support_metrics} with discount {discount}. "
            )
            logger.error(error_message)
            error_payload = {
                "service_name": AWSServiceEnum.SUPPORT.value,
                "amount": 0,
            }
            raise AWSBillingError(error_message, error_payload)

        support = next(iter(support_metrics.values()), 0)
        support_discount = discount / support * 100 if support != 0 else 0
        return round(abs(support_discount))


class SupportDiscountValidator(DiscountValidator):
    """Discount validator for AWS support services."""
    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        refund_metrics = account_metrics.get(UsageMetricTypeEnum.REFUND.value, {})
        refund_discount = next(iter(refund_metrics.values()), 0)
        support_discount = self._get_support_discount(
            account_metrics.get(UsageMetricTypeEnum.SUPPORT.value, {}), refund_discount
        )
        return support_discount == discount


class SupportEnterpriseDiscountValidator(DiscountValidator):
    """Discount validator for AWS support enterprise services."""
    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        support_metrics = account_metrics.get(UsageMetricTypeEnum.SUPPORT.value, {})
        provider_discount_metrics = account_metrics.get(
            UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {}
        )
        support_name = next(iter(support_metrics.keys()), 0)
        provider_discount = abs(provider_discount_metrics.get(support_name, 0))
        support_discount = self._get_support_discount(support_metrics, provider_discount)
        return support_discount == discount


class DefaultDiscountValidator(DiscountValidator):
    """Default discount validator for AWS services."""
    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        partner_discounts = account_metrics.get(UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {})
        service_discount = partner_discounts.get(service_name, 0)
        provider_discount = self._calculate_provider_discount(service_discount, amount)

        is_discount_mismatch = discount == 0 and provider_discount != 0
        is_tolerance_exceeded = abs(provider_discount - discount) > tolerance_rate

        return not (is_discount_mismatch or is_tolerance_exceeded)


class UsageDiscountValidator(DiscountValidator):
    """Discount validator for AWS usage and recurring services."""
    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        usage = account_metrics.get(UsageMetricTypeEnum.USAGE.value, {})
        recurring = account_metrics.get(UsageMetricTypeEnum.RECURRING.value, {})
        provider_discounts = account_metrics.get(UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {})

        total_amount = usage.get(service_name, 0.0) + recurring.get(service_name, 0.0)

        service_discount = provider_discounts.get(service_name, 0)
        provider_discount = self._calculate_provider_discount(service_discount, total_amount)

        return not abs(provider_discount - discount) > tolerance_rate:
            return False
        return True


class DefaultTrueDiscountValidator(DiscountValidator):
    """Validator that returns True."""
    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        return True


class GenerateItemJournalLines:
    """Base class for generating journal lines for different AWS billing items."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        self._metric_id = metric_id
        self._billing_discount_tolerance_rate = billing_discount_tolerance_rate
        self._discount = discount
        self._exclude_services = []
        self._dynamic_exclude_services = []
        self._validator = DefaultTrueDiscountValidator

    def _get_exclude_services(self, account_metrics):
        exclude_services = self._exclude_services
        if not self._dynamic_exclude_services:
            return exclude_services
        for dynamic_exclude_service in self._dynamic_exclude_services:
            exclude_services.extend(account_metrics.get(dynamic_exclude_service, {}).keys())

        return exclude_services

    def process(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        """Generate item journal lines."""
        journal_lines = []
        metric_data = account_metrics.get(self._metric_id, {})

        filtered_metrics = {
            s: a
            for s, a in metric_data.items()
            if s not in self._get_exclude_services(account_metrics)
        }
        for service_name, amount in filtered_metrics.items():
            if not self._validator().validate(
                self._discount,
                amount,
                service_name,
                account_metrics,
                self._billing_discount_tolerance_rate,
            ):
                continue
            invoice_entity = account_metrics.get(
                UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value, {}
            ).get(service_name, "")
            invoice_details = account_invoices.get("invoice_entities", {}).get(invoice_entity, {})

            invoice_id = invoice_details.get("invoice_id", "")
            payment_currency = invoice_details.get("payment_currency_code", "")
            base_currency = invoice_details.get("base_currency_code", "")
            if payment_currency != base_currency:
                exchange_rate = invoice_details.get("exchange_rate", 0.0)
                amount = round(amount * exchange_rate, 6)
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


class GenerateMarketplaceJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS Marketplace usage metrics."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        super().__init__(metric_id, billing_discount_tolerance_rate, discount=discount)

        self._exclude_services = [AWSServiceEnum.TAX]
        self._validator = DefaultTrueDiscountValidator


class GenerateUsageJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS usage metrics."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        super().__init__(metric_id, billing_discount_tolerance_rate, discount=discount)

        self._exclude_services = [AWSServiceEnum.SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE]
        self._validator = UsageDiscountValidator


class GenerateSavingPlansJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS Saving Plans metrics."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        super().__init__(metric_id, billing_discount_tolerance_rate, discount=discount)

<<<<<<< HEAD
    _exclude_services = []
    _validator = DefaultDiscountValidator
=======
        self._exclude_services = []
        self._validator = DefaultTrueDiscountValidator
>>>>>>> 6a7ad8a (MPT-11915 Update code related to ruff rules in AWS extension code)


class GenerateOtherServicesJournalLines(GenerateItemJournalLines):
    """Generate journal lines for other AWS services excluding usage and marketplace services."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        super().__init__(metric_id, billing_discount_tolerance_rate, discount=discount)

<<<<<<< HEAD
    _exclude_services = [
        AWSServiceEnum.TAX.value,
        AWSServiceEnum.REFUND.value,
        AWSServiceEnum.SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE.value,
    ]
    _dynamic_exclude_services = [
        UsageMetricTypeEnum.MARKETPLACE.value,
        UsageMetricTypeEnum.SUPPORT.value,
    ]
    _validator = DefaultDiscountValidator
=======
        self._exclude_services = [
            AWSServiceEnum.TAX,
            AWSServiceEnum.REFUND,
            AWSServiceEnum.SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE,
        ]
        self._dynamic_exclude_services = [
            UsageMetricTypeEnum.MARKETPLACE.value,
            UsageMetricTypeEnum.SUPPORT.value,
        ]
        self._validator = DefaultDiscountValidator
>>>>>>> 6a7ad8a (MPT-11915 Update code related to ruff rules in AWS extension code)


class GenerateSupportJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS support usage metrics."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        super().__init__(metric_id, billing_discount_tolerance_rate, discount=discount)

        self._exclude_services = []
        self._validator = SupportDiscountValidator


class GenerateSupportEnterpriseJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS support enterprise usage metrics."""
    def __init__(self, metric_id, billing_discount_tolerance_rate, discount=None):
        super().__init__(metric_id, billing_discount_tolerance_rate, discount=discount)

        self._exclude_services = []
        self._validator = SupportEnterpriseDiscountValidator
