import logging

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import (
    TRANSFER_ACCOUNT_INVITATION_FOR_GENERIC_STATE,
    TRANSFER_ACCOUNT_INVITATION_NOTE,
    AwsHandshakeStateEnum,
    OrderProcessingTemplateEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
    StateMessageError,
)
from swo_aws_extension.flows.error import ERR_AWAITING_INVITATION_RESPONSE
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_QUERYING,
    PurchaseContext,
)
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_phase,
    list_ordering_parameters_with_errors,
    prepare_parameters_for_querying,
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
        expected_phases = [
            PhasesEnum.TRANSFER_ACCOUNT,
            PhasesEnum.CHECK_INVITATION_LINK,
        ]
        if phase not in expected_phases:
            logger.info(
                f"{context.order_id} - Skip - Order is not in {", ".join(expected_phases)} phase. "
                f"Current phase is {phase}"
            )
            next_step(client, context)
            return
        assert context.aws_client is not None, "AWS client is not set in context"

        handshakes = context.aws_client.list_handshakes_for_organization()
        account_states = map_handshakes_account_state(handshakes)
        account_handshake_id = map_handshakes_account_handshake_id(handshakes)

        errors = []

        self.cancel_invitations_for_removed_accounts(
            context, account_handshake_id, account_states, errors
        )

        if errors:
            logger.info(f"{context.order_id} - Stop - Failed to cancel invitations.")
            return
        note = TRANSFER_ACCOUNT_INVITATION_NOTE.format(context=context)
        self.send_invitations_for_accounts(context, account_states, errors, note)

        if errors:
            logger.info(
                f"{context.order_id} - Stop - Failed to send organization invitation links."
            )
            return
        context.order = set_phase(context.order, PhasesEnum.CHECK_INVITATION_LINK)
        context.order = update_order(
            client,
            context.order_id,
            parameters=context.order["parameters"],
            template=context.template,
        )
        logger.info(f"{context.order_id} - Phase - Updated to {PhasesEnum.CHECK_INVITATION_LINK}")
        logger.info(f"{context.order_id} - Next - Invitation links sent to all accounts.")
        next_step(client, context)

    def send_invitations_for_accounts(self, context, account_states, errors, notes):
        not_send_invite_states = [
            AwsHandshakeStateEnum.OPEN,
            AwsHandshakeStateEnum.REQUESTED,
            AwsHandshakeStateEnum.DECLINED,
            AwsHandshakeStateEnum.CANCELED,
            AwsHandshakeStateEnum.ACCEPTED,
        ]

        for account_id in context.get_account_ids():
            account_state = account_states.get(account_id)
            if account_state in not_send_invite_states:
                logger.info(
                    f"{context.order_id} - Skip - Invitation link already sent to account. "
                    f"Invitation state='{account_state}' for account_id={account_id}"
                )
                continue
            try:
                context.aws_client.invite_account_to_organization(account_id, notes=notes)
                logger.info(
                    f"{context.order_id} - Action - Invitation link sent to account {account_id} "
                    f"state '{account_state}'"
                )
            except Exception as e:
                errors.append(e)
                logger.exception(
                    f"{context.order_id} - Action Failed - Invitation for `{account_id}` failed."
                    f"  state '{account_state}'"
                    f"Reason: {str(e)}"
                )

    def cancel_invitations_for_removed_accounts(
        self, context, account_handshake_id, account_state, errors
    ):
        cancellable_states = [AwsHandshakeStateEnum.REQUESTED, AwsHandshakeStateEnum.OPEN]
        for account_id, state in account_state.items():
            if account_id in context.get_account_ids():
                continue
            logger.info(
                f"{context.order_id} - Account {account_id} not in transfer accounts "
                f"but found while listing handshakes with state `{state}`"
            )
            if state not in cancellable_states:
                if state == AwsHandshakeStateEnum.CANCELED:
                    continue
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
    def accounts_state_message_building(self, account_state):
        """
        Build a message with the accounts and their states.
        :param pending_accounts_by_state: Dictionary with account IDs and their states.
        :return: String with the accounts and their states.
        """

        message_map = {
            AwsHandshakeStateEnum.REQUESTED: StateMessageError.REQUESTED,
            AwsHandshakeStateEnum.OPEN: StateMessageError.OPEN,
            AwsHandshakeStateEnum.CANCELED: StateMessageError.CANCELED,
            AwsHandshakeStateEnum.DECLINED: StateMessageError.DECLINED,
            AwsHandshakeStateEnum.EXPIRED: StateMessageError.EXPIRED,
        }
        message = []
        for account, state in account_state.items():
            if state in message_map:
                message.append(message_map[state].format(account=account, state=state.capitalize()))
            else:
                message.append(
                    TRANSFER_ACCOUNT_INVITATION_FOR_GENERIC_STATE.format(
                        account=account, state=state
                    )
                )
                logger.warning(f"Unexpected state {state} for account {account}.")
        return "; ".join(message)

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
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_INVITATION_LINK:
            logger.info(
                f"{context.order_id} - Skip - Reason: Expecting phase in"
                f" {PhasesEnum.CHECK_INVITATION_LINK}, current "
                f"phase={phase}"
            )
            next_step(client, context)
            return
        terminal_states = {AwsHandshakeStateEnum.ACCEPTED}
        handshakes = context.aws_client.list_handshakes_for_organization()
        account_state = map_handshakes_account_state(handshakes)

        pending_account_state = {
            account: state
            for account, state in account_state.items()
            if account in context.get_account_ids() and state not in terminal_states
            if state not in terminal_states
        }

        if pending_account_state:
            # If all accounts has not accepted the invitation, we set the order to query
            str_accounts = self.accounts_state_message_building(pending_account_state)
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_AWAITING_INVITATION_RESPONSE.to_dict(accounts=str_accounts),
            )
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            if context.order_status != MPT_ORDER_STATUS_QUERYING:
                context.switch_order_status_to_query(
                    client, OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS
                )
            else:
                context.update_processing_template(
                    client,
                    OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS,
                )
            logger.info(
                f"{context.order_id} - Querying - Awaiting account invitations to be accepted: "
                f"{str_accounts}"
            )
            return

        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS)
        template_name = OrderProcessingTemplateEnum.TRANSFER_WITH_ORG_TICKET_CREATED
        if context.order_status == MPT_ORDER_STATUS_QUERYING:
            context.switch_order_status_to_process(client, template_name)
        else:
            context.update_processing_template(client, template_name)
        logger.info(f"{context.order_id} - Success - Invitation links completed.")
        next_step(client, context)
