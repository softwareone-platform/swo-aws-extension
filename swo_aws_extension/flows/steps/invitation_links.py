import logging

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.error import ERR_AWAITING_INVITATION_RESPONSE
from swo_aws_extension.flows.order import PurchaseContext, switch_order_to_query
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_phase,
    set_ordering_parameter_error,
    set_phase,
)

logger = logging.getLogger(__name__)


def get_handshake_account_id(handshake):
    for p in handshake["Parties"]:
        if p["Type"] == "ACCOUNT":
            account_id = p["Id"]
            return account_id


def map_handshakes_account_state(handshakes):
    """
    Process handshakes to check if they are in the correct state.
    :param context: The context of the order.
    :param handshakes: List of handshakes to process.
    :return: Dictionary with account IDs and their states.
    """

    handshakes_dict = {
        get_handshake_account_id(handshake): handshake["State"] for handshake in handshakes
    }
    return handshakes_dict


def map_handshakes_account_handshake_id(handshakes):
    """
    Process handshakes to check if they are in the correct state.
    :param context: The context of the order.
    :param handshakes: List of handshakes to process.
    :return: Dictionary with account IDs and their states.
    """

    handshakes_dict = {
        get_handshake_account_id(handshake): handshake["Id"] for handshake in handshakes
    }
    return handshakes_dict


class SendInvitationLinksStep(Step):
    def __call__(
        self,
        client: MPTClient,
        context: PurchaseContext,
        next_step: NextStep,
    ) -> None:
        """
        Check invited accounts to the organization.
        io
        - For accounts invited in State=REQUEST and removed from the order, cancel the invitation.
        - For accounts not invited and not removed from the order, send the invitation.


        For each account in context.get_account_ids()
        if no link has been sent to the account,
        send an invitation to join the aws organization
        """
        phase = get_phase(context.order)
        if phase != PhasesEnum.TRANSFER_ACCOUNT:
            logger.info(
                f"{context.order_id} - Skip - Order is not in TRANSFER_ACCOUNT phase. "
                f"Current phase is {phase}"
            )
            next_step(client, context)
            return
        assert context.aws_client is not None, "AWS client is not set in context"

        handshakes = context.aws_client.list_handshakes_for_organization()
        account_state = map_handshakes_account_state(handshakes)
        account_handshake_id = map_handshakes_account_handshake_id(handshakes)

        notes = f"Softwareone invite for order {context.order_id}"
        errors = []

        self.cancel_invitations_for_removed_accounts(
            context, account_handshake_id, account_state, errors
        )

        if errors:
            logger.info(f"{context.order_id} - Stop - Failed to cancel invitations.")
            return

        self.send_invitations_for_accounts(context, account_state, errors, notes)

        if errors:
            logger.info(
                f"{context.order_id} - Stop - Failed to send organization invitation links."
            )
            return

        logger.info(f"{context.order_id} - Next - Invitation links sent to all accounts.")
        next_step(client, context)

    def send_invitations_for_accounts(self, context, account_state, errors, notes):
        for account_id in context.get_account_ids():
            if account_id in account_state.keys():
                logger.info(
                    f"{context.order_id} - Skip - Invitation link already sent to account "
                    f"{account_id}"
                )
                continue
            try:
                context.aws_client.invite_account_to_organization(account_id, notes=notes)
                logger.info(
                    f"{context.order_id} - Action - Invitation link sent to account {account_id}"
                )
            except Exception as e:
                errors.append(e)
                logger.exception(
                    f"{context.order_id} - Action Failed - Invitation for `{account_id}` failed. "
                    f"Reason: {str(e)}"
                )

    def cancel_invitations_for_removed_accounts(
        self, context, account_handshake_id, account_state, errors
    ):
        cancellable_states = ["OPEN", "REQUESTED"]
        for account_id, state in account_state.items():
            if account_id in context.get_account_ids():
                continue
            logger.info(
                f"{context.order_id} - Account {account_id} not in accounts but in handshakes "
                f"with state `{state}`"
            )
            if state not in cancellable_states:
                logger.info(
                    f"{context.order_id} - Action cancelled - "
                    f"Unable to cancel handshake for {account_id}. Reason: "
                    f"Current state `{state}` is not cancelable. "
                    f"Cancelable states are: {",".join(cancellable_states)}"
                )
                continue
            handshake_id = account_handshake_id[account_id]
            try:
                context.aws_client.cancel_handshake(handshake_id)
                logger.info(
                    f"{context.order_id} - Action - "
                    f"Cancel handshake `{handshake_id}` for Account: {account_id}"
                )
            except Exception as e:
                logger.exception(
                    f"{context.order_id} - Action failed - Cancel handshake `{handshake_id}` for "
                    f"account_id `{account_id}` failed. Reason: {str(e)}"
                )
                errors.append(e)


class AwaitInvitationLinksStep(Step):
    def __call__(
        self,
        client: MPTClient,
        context: PurchaseContext,
        next_step: NextStep,
    ) -> None:
        """
        Wait for all invitation links to reach a terminal state.

        :param client: The MPT client.
        :param context: The purchase context.
        :param next_step: The next step in the pipeline.
        """
        if get_phase(context.order) != PhasesEnum.TRANSFER_ACCOUNT:
            logger.info(f"{context.order_id} - Skip - Invitation links already completed.")
            next_step(client, context)
            return
        terminal_states = {"ACCEPTED"}
        handshakes = context.aws_client.list_handshakes_for_organization()
        account_state = map_handshakes_account_state(handshakes)

        pending_accounts = [
            account_id
            for account_id in context.get_account_ids()
            if account_state.get(account_id) not in terminal_states
        ]

        if pending_accounts:
            # If all accounts has not accepted the invitation, we set the order to query
            str_accounts = {", ".join(pending_accounts)}
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_AWAITING_INVITATION_RESPONSE.to_dict(accounts=str_accounts),
            )
            switch_order_to_query(client, context.order)
            logger.info(
                f"{context.order_id} - Querying - Awaiting account invitations to be accepted: "
                f"{str_accounts}"
            )
            return

        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
        logger.info(f"{context.order_id} - Success - Invitation links completed.")
        next_step(client, context)
