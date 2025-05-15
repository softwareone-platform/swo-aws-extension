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
            return OrderProcessingTemplateEnum.CHANGE

        if context.order_type == ORDER_TYPE_TERMINATION:
            return OrderProcessingTemplateEnum.TERMINATION

        if get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT:
            if context.is_split_billing():
                return OrderProcessingTemplateEnum.SPLIT_BILLING

            if context.is_type_transfer_without_organization():
                return OrderProcessingTemplateEnum.TRANSFER_WITHOUT_ORG

            return OrderProcessingTemplateEnum.TRANSFER_WITH_ORG
        # New account

        return OrderProcessingTemplateEnum.NEW_ACCOUNT

    @staticmethod
    def complete(context: InitialAWSContext) -> str:
        if context.order_type == ORDER_TYPE_CHANGE:
            return OrderCompletedTemplateEnum.CHANGE

        if context.order_type == ORDER_TYPE_TERMINATION:
            if (
                get_termination_type_parameter(context.order)
                == TerminationParameterChoices.CLOSE_ACCOUNT
            ):
                return OrderCompletedTemplateEnum.TERMINATION_TERMINATE
            return OrderCompletedTemplateEnum.TERMINATION_DELINK

        if get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT:
            if context.is_split_billing():
                return OrderCompletedTemplateEnum.SPLIT_BILLING

            if context.is_type_transfer_without_organization():
                if context.pls_enabled:
                    return OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITH_PLS
                return OrderCompletedTemplateEnum.TRANSFER_WITHOUT_ORG_WITHOUT_PLS
            if context.pls_enabled:
                return OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITH_PLS
            return OrderCompletedTemplateEnum.TRANSFER_WITH_ORG_WITHOUT_PLS

        # New account
        if context.pls_enabled:
            return OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS
        return OrderCompletedTemplateEnum.NEW_ACCOUNT_WITHOUT_PLS
