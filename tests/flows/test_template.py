import pytest
from mpt_extension_sdk.flows.context import (
    ORDER_TYPE_CHANGE,
    ORDER_TYPE_PURCHASE,
    ORDER_TYPE_TERMINATION,
)

from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderCompletedTemplateEnum,
    OrderProcessingTemplateEnum,
    SupportTypesEnum,
    TerminationParameterChoices,
    TransferTypesEnum,
)
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.template import TemplateNameManager


@pytest.mark.parametrize(
    (
        "order_type",
        "account_type",
        "transfer_type",
        "support_type",
        "termination_type",
        "expected_template",
    ),
    [
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.NEW_ACCOUNT,
            "",
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS,
        ),
        (
            AccountTypesEnum.NEW_ACCOUNT,
            "",
            SupportTypesEnum.RESOLD_SUPPORT,
            ORDER_TYPE_PURCHASE,
            "",
            OrderCompletedTemplateEnum.NEW_ACCOUNT_WITHOUT_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.SPLIT_BILLING,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderCompletedTemplateEnum.SPLIT_BILLING,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITH_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            SupportTypesEnum.RESOLD_SUPPORT,
            "",
            OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITHOUT_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITH_PLS,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            SupportTypesEnum.RESOLD_SUPPORT,
            "",
            OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITHOUT_PLS,
        ),
        (ORDER_TYPE_CHANGE, "", "", "", "", OrderCompletedTemplateEnum.CHANGE),
        (
            ORDER_TYPE_TERMINATION,
            "",
            "",
            "",
            TerminationParameterChoices.CLOSE_ACCOUNT,
            OrderCompletedTemplateEnum.TERMINATION_TERMINATE,
        ),
        (
            ORDER_TYPE_TERMINATION,
            "",
            "",
            "",
            TerminationParameterChoices.UNLINK_ACCOUNT,
            OrderCompletedTemplateEnum.TERMINATION_DELINK,
        ),
    ],
)
def test_template_name_manager_complete(
    account_type: AccountTypesEnum,
    support_type: SupportTypesEnum,
    transfer_type: TransferTypesEnum,
    order_type,
    termination_type,
    expected_template: OrderCompletedTemplateEnum,
    order_factory,
    order_parameters_factory,
):
    order = order_factory(
        order_type=order_type,
        order_parameters=order_parameters_factory(
            account_type=account_type,
            support_type=support_type,
            transfer_type=transfer_type,
            termination_type=termination_type,
        ),
    )
    context = InitialAWSContext.from_order_data(order)
    assert TemplateNameManager.complete(context) == expected_template


@pytest.mark.parametrize(
    (
        "order_type",
        "account_type",
        "transfer_type",
        "support_type",
        "termination_type",
        "expected_template",
    ),
    [
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.NEW_ACCOUNT,
            "",
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderProcessingTemplateEnum.NEW_ACCOUNT,
        ),
        (
            AccountTypesEnum.NEW_ACCOUNT,
            "",
            SupportTypesEnum.RESOLD_SUPPORT,
            ORDER_TYPE_PURCHASE,
            "",
            OrderProcessingTemplateEnum.NEW_ACCOUNT,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.SPLIT_BILLING,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderProcessingTemplateEnum.SPLIT_BILLING,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderProcessingTemplateEnum.TRANSFER_WITH_ORG,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            SupportTypesEnum.RESOLD_SUPPORT,
            "",
            OrderProcessingTemplateEnum.TRANSFER_WITH_ORG,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            SupportTypesEnum.PARTNER_LED_SUPPORT,
            "",
            OrderProcessingTemplateEnum.TRANSFER_WITHOUT_ORG,
        ),
        (
            ORDER_TYPE_PURCHASE,
            AccountTypesEnum.EXISTING_ACCOUNT,
            TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            SupportTypesEnum.RESOLD_SUPPORT,
            "",
            OrderProcessingTemplateEnum.TRANSFER_WITHOUT_ORG,
        ),
        (ORDER_TYPE_CHANGE, "", "", "", "", OrderProcessingTemplateEnum.CHANGE),
        (
            ORDER_TYPE_TERMINATION,
            "",
            "",
            "",
            TerminationParameterChoices.CLOSE_ACCOUNT,
            OrderProcessingTemplateEnum.TERMINATION,
        ),
        (
            ORDER_TYPE_TERMINATION,
            "",
            "",
            "",
            TerminationParameterChoices.UNLINK_ACCOUNT,
            OrderProcessingTemplateEnum.TERMINATION,
        ),
    ],
)
def test_template_name_manager_processing(
    account_type: AccountTypesEnum,
    support_type: SupportTypesEnum,
    transfer_type: TransferTypesEnum,
    order_type,
    termination_type,
    expected_template: OrderProcessingTemplateEnum,
    order_factory,
    order_parameters_factory,
):
    order = order_factory(
        order_type=order_type,
        order_parameters=order_parameters_factory(
            account_type=account_type,
            support_type=support_type,
            transfer_type=transfer_type,
            termination_type=termination_type,
        ),
    )
    context = InitialAWSContext.from_order_data(order)
    assert TemplateNameManager.processing(context) == expected_template
