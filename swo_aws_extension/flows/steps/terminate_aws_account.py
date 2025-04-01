import logging

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.aws.errors import (
    AWSRequerimentsNotMeetError,
    AWSTerminationCoolOffPeriodError,
    AWSTerminationQuotaError,
)
from swo_aws_extension.constants import TerminationParameterChoices
from swo_aws_extension.flows.error import (
    ERR_TERMINATION_AWS,
    ERR_TERMINATION_TYPE_EMPTY,
)
from swo_aws_extension.flows.order import TerminateContext, switch_order_to_query
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_crm_ticket_id,
    get_termination_type_parameter,
    set_ordering_parameter_error,
)

logger = logging.getLogger(__name__)


class TerminateAWSAccount(Step):
    def aws_ids_to_terminate(self, context):
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
        context: TerminateContext,
        next_step: NextStep,
    ) -> None:
        crm_ticket_id = get_crm_ticket_id(context.order)
        if crm_ticket_id:
            """
            If the ticket is already set.
            we are waiting for the ticket to be closed and MPA to be terminated
            """
            logger.info(
                f"{context.order_id} - Skipping - Ticket already set. ticket_id=`{crm_ticket_id}`"
            )
            next_step(client, context)
            return
        for_termination = self.aws_ids_to_terminate(context)
        if not for_termination:
            logger.info(f"{context.order_id} - Skipping - No accounts to terminate")
            next_step(client, context)
            return
        account_id = for_termination.pop(0)
        termination_type = get_termination_type_parameter(context.order)

        if not termination_type:
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.TERMINATION,
                ERR_TERMINATION_TYPE_EMPTY.to_dict(),
            )
            context.order = switch_order_to_query(client, context.order)
            logger.info(f"{context.order_id} - Querying - {ERR_TERMINATION_TYPE_EMPTY}")
            return
        try:
            if termination_type == TerminationParameterChoices.CLOSE_ACCOUNT:
                context.aws_client.close_account(account_id)
                logger.info(f"{context.order_id} - Action - Closed AWS Account {account_id}")
            elif termination_type == TerminationParameterChoices.UNLINK_ACCOUNT:
                context.aws_client.remove_account_from_organization(account_id)
                logger.info(f"{context.order_id} - Action - Unlinked AWS Account {account_id}")
        except AWSTerminationCoolOffPeriodError as cool_off_exception:
            """
            If the account is in a cool off period, we will not terminate it.
            An account can't be terminated if it was created less than 7 days ago.

            You can close only 10% of member accounts, between 10 and 1000,
            within a rolling 30 day period.
            """
            logger.info(
                f"{context.order_id} - Stopping - Awaiting: AWS Account "
                f"`{cool_off_exception.account_id}` could not be terminated right now due to "
                f"cool off period. An account can't be terminated in the first 7 days."
            )
            return
        except AWSRequerimentsNotMeetError as exception:
            """
                botocore.errorfactory.ConstraintViolationException: An error occurred
                (ConstraintViolationException) when calling the RemoveAccountFromOrganization
                operation: The member account is missing one or more of the prerequisites
                required to operate as a standalone account. To add what is missing, sign-in to
                the member account using the AWS Organizations console, then select to leave
                the organization. You will then be prompted to enter any missing information.
            """
            error = ValidationError(
                ERR_TERMINATION_AWS.id,
                ERR_TERMINATION_AWS.message.format(member_account=exception.account_id),
            )
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.TERMINATION,
                error.to_dict(),
            )
            context.order = switch_order_to_query(client, context.order)
            logger.info(
                f"{context.order_id} - Querying - Order updated to Querying. "
                f"The member account `{exception.account_id}` of MPA `{context.mpa_account}` "
                f"is missing requirements for terminating type `{termination_type}`"
            )
            return
        except AWSTerminationQuotaError as exception:
            logger.info(
                f"{context.order_id} - Stopping - Awaiting: AWS terminate account quota reached "
                f"for MPA `{context.mpa_account}` while attempting {exception.method} "
                f"for account id `{exception.account_id}`. "
                f"You can only terminate 10% of your AWS Accounts for 30 days."
            )
            return

        # Check if there are more accounts to terminate
        if len(for_termination) > 0:
            # We close only one account at a time due to rate limits
            # https://docs.aws.amazon.com/organizations/latest/userguide/orgs_reference_limits.html
            logger.info(
                f"{context.order_id} - Stopping - More accounts to terminate. "
                f"Avoiding rate limits."
            )
            return

        next_step(client, context)
