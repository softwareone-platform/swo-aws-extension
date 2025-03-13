from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import NextStep, Step

from swo_aws_extension.flows.order import CloseAccountContext
from swo_aws_extension.parameters import get_account_id


class CloseAWSAccountStep(Step):
    def __call__(
            self,
            client: MPTClient,
            context: CloseAccountContext,
            next_step: NextStep,
    ) -> None:
        account_id = get_account_id(context.order)
        if account_id is None:
            raise ValueError("Account ID is required.")
        context.aws_client.close_account(account_id)
        next_step(client, context)
