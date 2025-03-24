import logging

from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import NextStep, Step

from swo_aws_extension.flows.order import CloseAccountContext

logger = logging.getLogger(__name__)


class CloseAWSAccountStep(Step):

    def aws_ids_to_close(self, context):
        """
        Get the list of AWS account IDs that are int termination process and still ACTIVE

        :param context:
        :return:
        """
        accounts = context.aws_client.list_accounts()
        accounts_to_terminate_ids = context.terminating_subscriptions_aws_account_ids
        active_accounts_id = [
            account["Id"] for account in accounts if account["Status"] == "ACTIVE"
        ]
        result = list(set(accounts_to_terminate_ids).intersection(active_accounts_id))
        result.sort()
        return result

    def __call__(
        self,
        client: MPTClient,
        context: CloseAccountContext,
        next_step: NextStep,
    ) -> None:

        accounts_to_close = self.aws_ids_to_close(context)
        if not accounts_to_close:
            logger.debug(f"{context.order_id} - No accounts to close")
            next_step(client, context)
            return
        account_id = accounts_to_close.pop(0)
        context.aws_client.close_account(account_id)
        logger.info(f"{context.order_id} - Closed AWS Account {account_id}")
        if len(accounts_to_close) > 0:
            # We close only one account at a time due to rate limits
            # https://docs.aws.amazon.com/organizations/latest/userguide/orgs_reference_limits.html
            return

        next_step(client, context)
