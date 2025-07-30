from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE, ORDER_TYPE_TERMINATION

from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderCompletedTemplateEnum,
    OrderProcessingTemplateEnum,
    TerminationParameterChoices,
)
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.parameters import get_account_type, get_termination_type_parameter


class TemplateNameManager:
    @staticmethod
    def processing(context: InitialAWSContext) -> str:
        if context.order_type == ORDER_TYPE_CHANGE:
            return OrderProcessingTemplateEnum.CHANGE.value

        if context.order_type == ORDER_TYPE_TERMINATION:
            return OrderProcessingTemplateEnum.TERMINATION.value

        if get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT:
            if context.is_split_billing():
                return OrderProcessingTemplateEnum.SPLIT_BILLING.value

            if context.is_type_transfer_without_organization():
                return OrderProcessingTemplateEnum.TRANSFER_WITHOUT_ORG.value

            return OrderProcessingTemplateEnum.TRANSFER_WITH_ORG.value
        # New account

        return OrderProcessingTemplateEnum.NEW_ACCOUNT.value

    @staticmethod
    def complete(context: InitialAWSContext) -> str:
        if context.order_type == ORDER_TYPE_CHANGE:
            return OrderCompletedTemplateEnum.CHANGE.value

        if context.order_type == ORDER_TYPE_TERMINATION:
            if (
                get_termination_type_parameter(context.order)
                == TerminationParameterChoices.CLOSE_ACCOUNT
            ):
                return OrderCompletedTemplateEnum.TERMINATION_TERMINATE.value
            return OrderCompletedTemplateEnum.TERMINATION_DELINK.value

        if get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT:
            if context.is_split_billing():
                return OrderCompletedTemplateEnum.SPLIT_BILLING.value

            if context.is_type_transfer_without_organization():
                if context.pls_enabled:
                    return OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITH_PLS.value
                return OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITHOUT_PLS.value
            if context.pls_enabled:
                return OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITH_PLS.value
            return OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITHOUT_PLS.value

        # New account
        if context.pls_enabled:
            return OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS.value
        return OrderCompletedTemplateEnum.NEW_ACCOUNT_WITHOUT_PLS.value
