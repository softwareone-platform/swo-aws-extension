from decimal import Decimal

from swo_aws_extension.constants import UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultDiscountValidator,
    DefaultTrueDiscountValidator,
    SupportDiscountValidator,
    UsageDiscountValidator,
)


def test_support_discount_validator(config):
    validator = SupportDiscountValidator()
    account_metrics = {
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: {"AWS Support (Enterprise)": Decimal("35.0")}
    }

    validate_result = validator.validate(
        discount=config.billing_discount_support_enterprise,
        amount=Decimal("100.0"),
        service_name="AWS Support (Enterprise)",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert validate_result


def test_support_discount_validator_exceeds(config):
    validator = SupportDiscountValidator()
    account_metrics = {
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: {"AWS Support (Business)": Decimal("20.0")}
    }

    validate_result = validator.validate(
        discount=config.billing_discount_base,
        amount=Decimal("100.0"),
        service_name="AWS Support (Business)",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert not validate_result


def test_default_validator_zero_discount(config):
    validator = DefaultDiscountValidator()
    account_metrics = {
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: {"Service Name": Decimal("10.0")}
    }

    validate_result = validator.validate(
        discount=0,
        amount=Decimal("100.0"),
        service_name="Service Name",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert not validate_result


def test_default_validator_within_tolerance(config):
    validator = DefaultDiscountValidator()
    account_metrics = {
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: {"Service Name": Decimal("7.0")}
    }

    validate_result = validator.validate(
        discount=config.billing_discount_base,
        amount=Decimal("100.0"),
        service_name="Service Name",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert validate_result


def test_usage_validator_usage_and_recurring(config):
    validator = UsageDiscountValidator()
    account_metrics = {
        UsageMetricTypeEnum.USAGE.value: {"Service Name": Decimal("70.0")},
        UsageMetricTypeEnum.RECURRING.value: {"Service Name": Decimal("30.0")},
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: {"Service Name": Decimal("7.0")},
    }

    validate_result = validator.validate(
        discount=config.billing_discount_base,
        amount=Decimal("100.0"),
        service_name="Service Name",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert validate_result


def test_usage_validator_exceeds_tolerance(config):
    validator = UsageDiscountValidator()
    account_metrics = {
        UsageMetricTypeEnum.USAGE.value: {"Service Name": Decimal("40.0")},
        UsageMetricTypeEnum.RECURRING.value: {"Service Name": Decimal("40.0")},
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: {"Service Name": Decimal("12.0")},
    }

    validate_result = validator.validate(
        discount=config.billing_discount_incentivate,
        amount=Decimal("0.0"),
        service_name="Service Name",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert not validate_result


def test_default_true_validator_always_true(config):
    validator = DefaultTrueDiscountValidator()
    account_metrics = {}

    validate_result = validator.validate(
        discount=config.billing_discount_base,
        amount=Decimal("0.0"),
        service_name="Service Name",
        account_metrics=account_metrics,
        tolerance_rate=config.billing_discount_tolerance_rate,
    )

    assert validate_result
