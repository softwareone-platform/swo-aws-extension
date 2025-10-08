from abc import ABC, abstractmethod
from typing import override

from swo_aws_extension.constants import UsageMetricTypeEnum


class DiscountValidator(ABC):
    """Base class for discount validation."""

    @abstractmethod
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        """Validate discount on AWS."""
        raise NotImplementedError

    def _calculate_provider_discount(self, discount, amount):
        partner_amount = amount - abs(discount)

        return 0 if amount == 0 else ((amount - partner_amount) / amount) * 100


class SupportDiscountValidator(DiscountValidator):
    """Discount validator for AWS support services."""

    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        provider_discount_metrics = account_metrics.get(
            UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {}
        )

        service_discount = provider_discount_metrics.get(service_name, 0)
        provider_discount = self._calculate_provider_discount(service_discount, amount)

        return abs(provider_discount - discount) <= tolerance_rate


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

        total_amount = usage.get(service_name, 0) + recurring.get(service_name, 0)
        provider_discount = self._calculate_provider_discount(
            provider_discounts.get(service_name, 0), total_amount
        )
        return abs(provider_discount - discount) <= tolerance_rate


class DefaultTrueDiscountValidator(DiscountValidator):
    """Validator that returns True."""

    @override
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        return True
