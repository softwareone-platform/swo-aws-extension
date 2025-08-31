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


def get_handshake_account_id(handshake: dict) -> str:
    """Retrieve acoount id from handshake."""
    for p in handshake["Parties"]:
        if p["Type"] == "ACCOUNT":
            return p["Id"]

    return None


def map_handshakes_account_state(handshakes: list[dict]) -> dict:
    """
    Process handshakes to check if they are in the correct state.

    Args:
        context: The context of the order.
        handshakes: List of handshakes to process.

    Returns:
        Dictionary with account IDs and their states.
    """
    return {
        get_handshake_account_id(handshake): handshake["State"] for handshake in handshakes
    }


def map_handshakes_account_handshake_id(handshakes: list[dict]) -> dict:
    """
    Process handshakes to check if they are in the correct state.

    Args:
        handshakes: List of handshakes to process.

    Returns:
        Dictionary with account IDs and their states.
    """
    return {
        get_handshake_account_id(handshake): handshake["Id"] for handshake in handshakes
    }


class SendInvitationLinksStep(Step):
    """Send invitation link to the customer."""
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step: NextStep):
        """
        Check invited accounts to the organization.

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
                "%s - Skip - Order is not in %s phase. Current phase is %s",
                context.order_id, ", ".join(expected_phases), phase
            )
            next_step(client, context)
            return
        if not context.aws_client:
            raise ValueError("AWS client is not set in context")

        handshakes = context.aws_client.list_handshakes_for_organization()
        account_states = map_handshakes_account_state(handshakes)
        account_handshake_id = map_handshakes_account_handshake_id(handshakes)

        errors = []

        self.cancel_invitations_for_removed_accounts(
            context, account_handshake_id, account_states, errors
        )

        if errors:
            logger.info("%s - Stop - Failed to cancel invitations.", context.order_id)
            return
        note = TRANSFER_ACCOUNT_INVITATION_NOTE.format(context=context)
        self.send_invitations_for_accounts(context, account_states, errors, note)

        if errors:
            logger.info(
                "%s - Stop - Failed to send organization invitation links.", context.order_id,
            )
            return
        context.order = set_phase(context.order, PhasesEnum.CHECK_INVITATION_LINK.value)
        context.order = update_order(
            client,
            context.order_id,
            parameters=context.order["parameters"],
            template=context.template,
        )
        logger.info(
            "%s - Phase - Updated to %s", context.order_id, PhasesEnum.CHECK_INVITATION_LINK.value,
        )
        logger.info("%s - Next - Invitation links sent to all accounts.", context.order_id)
        next_step(client, context)

    def send_invitations_for_accounts(self, context, account_states, errors, notes):
        """Send invitations to customers."""
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
                    "%s - Skip - Invitation link already sent to account. "
                    "Invitation state='%s' for account_id=%s",
                    context.order_id, account_state, account_id,
                )
                continue
            try:
                context.aws_client.invite_account_to_organization(account_id, notes=notes)
                logger.info(
                    "%s - Action - Invitation link sent to account %s state '%s'",
                    context.order_id, account_id, account_state,
                )
            except Exception as e:
                errors.append(e)
                logger.exception(
                    "%s - Action Failed - Invitation for `%s` failed.  state '%s'.",
                    context.order_id, account_id, account_state,
                )

    def cancel_invitations_for_removed_accounts(
        self, context, account_handshake_id, account_state, errors
    ):
        """Cancel invitations for removed accounts."""
        cancellable_states = [AwsHandshakeStateEnum.REQUESTED, AwsHandshakeStateEnum.OPEN]
        for account_id, state in account_state.items():
            if account_id in context.get_account_ids():
                continue
            logger.info(
                "%s - Account %s not in transfer accounts "
                "but found while listing handshakes with state `%s`",
                context.order_id, account_id, state,
            )
            if state not in cancellable_states:
                if state == AwsHandshakeStateEnum.CANCELED:
                    continue
                logger.info(
                    "%s - Action cancelled - Unable to cancel handshake for %s. Reason: "
                    "Current state `%s` is not cancelable. "
                    "Cancelable states are: %s",
                    context.order_id, account_id, state, ",".join(cancellable_states),
                )
                continue
            handshake_id = account_handshake_id[account_id]
            try:
                context.aws_client.cancel_handshake(handshake_id)
                logger.info(
                    "%s - Action - Cancel handshake `%s` for Account: %s",
                    context.order_id, handshake_id, account_id,
                )
            except Exception as e:
                logger.exception(
                    "%s - Action failed - Cancel handshake `%s` for account_id `%s` failed.",
                    context.order_id, handshake_id, account_id,
                )
                errors.append(e)


class AwaitInvitationLinksStep(Step):
    """Wait for invitation link to be accepted."""
    def accounts_state_message_building(self, account_state):
        """
        Build a message with the accounts and their states.

        Args:
            account_state: Dictionary with account IDs and their states.

        Returns:
            String with the accounts and their states.
        """
        message_map = {
            AwsHandshakeStateEnum.REQUESTED.value: StateMessageError.REQUESTED,
            AwsHandshakeStateEnum.OPEN.value: StateMessageError.OPEN,
            AwsHandshakeStateEnum.CANCELED.value: StateMessageError.CANCELED,
            AwsHandshakeStateEnum.DECLINED.value: StateMessageError.DECLINED,
            AwsHandshakeStateEnum.EXPIRED.value: StateMessageError.EXPIRED,
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
                logger.warning("Unexpected state %s for account %s.", state, account)
        return "; ".join(message)

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step: NextStep):
        """
        Wait for all invitation links to reach a terminal state.

        Args:
            client: The MPT client.
            context: The purchase context.
            next_step: The next step in the pipeline.
        """
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_INVITATION_LINK:
            logger.info(
                "%s - Skip - Reason: Expecting phase in %s, current phase=%s",
                context.order_id, PhasesEnum.CHECK_INVITATION_LINK.value, phase,
            )
            next_step(client, context)
            return
        terminal_states = {AwsHandshakeStateEnum.ACCEPTED.value}
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
                    client, OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS.value
                )
            else:
                context.update_processing_template(
                    client,
                    OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS.value,
                )
            logger.info(
                "%s - Querying - Awaiting account invitations to be accepted: %s",
                context.order_id, str_accounts,
            )
            return

        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS.value)
        template_name = OrderProcessingTemplateEnum.TRANSFER_WITH_ORG_TICKET_CREATED.value
        if context.order_status == MPT_ORDER_STATUS_QUERYING:
            context.switch_order_status_to_process(client, template_name)
        else:
            context.update_processing_template(client, template_name)
        logger.info("%s - Success - Invitation links completed.", context.order_id)
        next_step(client, context)
