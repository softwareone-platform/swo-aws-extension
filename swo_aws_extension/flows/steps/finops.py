import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext, TerminateContext
from swo_finops_client.client import get_ffc_client

logger = logging.getLogger(__name__)


def create_finops_entitlement(ffc_client, account_id, buyer_id, logger_header):
    """
    Create a FinOps entitlement for the given account ID if it does not already exist.
    Args:
        ffc_client: The FinOps client instance.
        account_id: The account ID to create the entitlement for.
        buyer_id: The buyer ID associated with the entitlement.
        logger_header: The header for the logger to identify the source of the log message.

    Returns:

    """
    entitlement = ffc_client.get_entitlement_by_datasource_id(account_id)
    if entitlement:
        logger.info(
            f"{logger_header} - Skipping - Entitlement already exists ({entitlement['id']}) "
            f"for account id {account_id}"
        )
    else:
        logger.info(f"{logger_header} - Action - Creating entitlement for account id {account_id}")
        entitlement = ffc_client.create_entitlement(buyer_id, account_id)
        logger.info(
            f"{logger_header} - Action - Created entitlement {entitlement['id']} for account id"
            f" {account_id}"
        )


class CreateFinOpsEntitlementStep(Step):
    """
    CreateFinOpsEntitlementStep is a step in the pipeline that creates a FinOps entitlement.
    It uses the FinOpsClient to create the entitlement.
    """

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        ffc_client = get_ffc_client()
        for subscription in context.subscriptions:
            create_finops_entitlement(
                ffc_client,
                subscription.get("externalIds", {}).get("vendor"),
                context.buyer["id"],
                context.order_id,
            )

        next_step(client, context)


class CreateFinOpsMPAEntitlementStep(Step):
    """
    CreateFinOpsEntitlementStep is a step in the pipeline that creates a FinOps entitlement.
    It uses the FinOpsClient to create the entitlement.
    """

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        ffc_client = get_ffc_client()
        logger.info(
            f"{context.order_id} - Action - Creating FinOps entitlement for MPA account "
            f"{context.mpa_account}"
        )
        create_finops_entitlement(
            ffc_client, context.mpa_account, context.buyer["id"], context.order_id
        )
        next_step(client, context)


def have_active_accounts(aws_client, mpa_account_id):
    """
    Check if there are any active accounts other than the management account.
    Args:
        aws_client: The AWS client instance.
        mpa_account_id: The management account ID.
    Returns:
        bool: True if there are active accounts other than the management account, False otherwise.

    """
    accounts = aws_client.list_accounts()
    return any(
        account["Id"] != mpa_account_id and account["Status"] == "ACTIVE" for account in accounts
    )


class DeleteFinOpsEntitlementsStep(Step):
    """
    DeleteFinOpsEntitlementStep is a step in the pipeline that deletes FinOps entitlements.
    It uses the FinOpsClient to delete the entitlement.
    """

    def __call__(self, client: MPTClient, context: TerminateContext, next_step):
        ffc_client = get_ffc_client()
        logger.info(f"{context.order_id} - Action - Terminate FinOps entitlements")
        for account_id in context.terminating_subscriptions_aws_account_ids:
            self.delete_entitlement(ffc_client, context, account_id)

        if not have_active_accounts(context.aws_client, context.mpa_account):
            ffc_client.terminate_entitlement(context.mpa_account)
            logger.info(
                f"{context.order_id} - Action - Terminated entitlement for MPA account i"
                f"d {context.mpa_account}"
            )

        logger.info(f"{context.order_id} - Next - Terminate FinOps entitlement completed")
        next_step(client, context)

    @staticmethod
    def delete_entitlement(ffc_client, context, account_id):
        """
        Delete the FinOps entitlement for the given account ID.
        Args:
            ffc_client: The FinOps client instance.
            context: The context of the current step.
            account_id: The account ID to delete the entitlement for.
        """

        entitlement = ffc_client.get_entitlement_by_datasource_id(account_id)
        if not entitlement:
            logger.info(
                f"{context.order_id} - Skip - Could not find entitlement for account id"
                f" {account_id}"
            )
            return
        if entitlement["status"] == "new":
            ffc_client.delete_entitlement(entitlement["id"])
            logger.info(
                f"{context.order_id} - Action - Deleted entitlement {entitlement['id']} "
                f"for account id {account_id}"
            )
        elif entitlement["status"] == "active":
            ffc_client.terminate_entitlement(entitlement["id"])
            logger.info(
                f"{context.order_id} - Action - Terminated entitlement {entitlement['id']}"
                f" for account id {account_id}"
            )
