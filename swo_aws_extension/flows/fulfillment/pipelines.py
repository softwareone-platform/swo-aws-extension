import logging
import re
import traceback

from mpt_extension_sdk.flows.context import Context
from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.config import Config
from swo_aws_extension.flows.steps.check_billing_transfer_invitation import (
    CheckBillingTransferInvitation,
)
from swo_aws_extension.flows.steps.check_channel_handshake_status import CheckChannelHandshakeStatus
from swo_aws_extension.flows.steps.check_customer_roles import CheckCustomerRoles
from swo_aws_extension.flows.steps.complete_order import CompleteOrder, CompleteTerminationOrder
from swo_aws_extension.flows.steps.configure_apn_program import ConfigureAPNProgram
from swo_aws_extension.flows.steps.create_billing_transfer_invitation import (
    CreateBillingTransferInvitation,
)
from swo_aws_extension.flows.steps.create_channel_handshake import CreateChannelHandshake
from swo_aws_extension.flows.steps.create_new_aws_environment import CreateNewAWSEnvironment
from swo_aws_extension.flows.steps.create_subscription import CreateSubscription
from swo_aws_extension.flows.steps.crm_tickets.deploy_customer_roles import (
    CRMTicketDeployCustomerRoles,
)
from swo_aws_extension.flows.steps.crm_tickets.new_account import CRMTicketNewAccount
from swo_aws_extension.flows.steps.crm_tickets.onboard_services import CRMTicketOnboardServices
from swo_aws_extension.flows.steps.crm_tickets.order_fail import CRMTicketOrderFail
from swo_aws_extension.flows.steps.crm_tickets.pls import CRMTicketPLS
from swo_aws_extension.flows.steps.crm_tickets.terminate_order import CRMTicketTerminateOrder
from swo_aws_extension.flows.steps.finops_entitlement import TerminateFinOpsEntitlementStep
from swo_aws_extension.flows.steps.onboard_services import OnboardServices
from swo_aws_extension.flows.steps.setup_context import SetupContext
from swo_aws_extension.flows.steps.terminate import TerminateResponsibilityTransferStep
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

config = Config()
logger = logging.getLogger(__name__)

TRACE_ID_REGEX = re.compile(r"(\(00-[0-9a-f]{32}-[0-9a-f]{16}-01\))")


def strip_trace_id(traceback_msg: str) -> str:
    """Strip trace id."""
    return TRACE_ID_REGEX.sub("(<omitted>)", traceback_msg)


# TODO This function is used to notify about unhandled exceptions in AWS pipelines.
# Should be removed with the new SDK error handling mechanism.
def pipeline_error_handler(error: Exception, context: Context, next_step):
    """Custom error handler for AWS pipelines."""
    logger.error("%s - Unexpected error in AWS pipeline: %s", context.order_id, error)
    traceback_id = strip_trace_id(traceback.format_exc())
    TeamsNotificationManager().notify_one_time_error(
        "Order fulfillment unhandled exception!",
        f"An unhandled exception has been raised while performing fulfillment "
        f"of the order **{context.order_id}**:\n\n"
        f"```{traceback_id}```",
    )
    raise error


purchase_new_aws_environment = Pipeline(
    SetupContext(config),
    CRMTicketNewAccount(config),
    CreateNewAWSEnvironment(config),
    CreateBillingTransferInvitation(config),
    CheckBillingTransferInvitation(config),
    ConfigureAPNProgram(config),
    CreateChannelHandshake(config),
    CheckChannelHandshakeStatus(config),
    CRMTicketDeployCustomerRoles(config),
    CheckCustomerRoles(config),
    CRMTicketOrderFail(config),
    OnboardServices(config),
    CreateSubscription(config),
    CRMTicketPLS(config),
    CRMTicketOnboardServices(config),
    CompleteOrder(config),
)

purchase_existing_aws_environment = Pipeline(
    SetupContext(config),
    CreateBillingTransferInvitation(config),
    CheckBillingTransferInvitation(config),
    ConfigureAPNProgram(config),
    CreateChannelHandshake(config),
    CheckChannelHandshakeStatus(config),
    CRMTicketDeployCustomerRoles(config),
    CheckCustomerRoles(config),
    CRMTicketOrderFail(config),
    OnboardServices(config),
    CreateSubscription(config),
    CRMTicketPLS(config),
    CRMTicketOnboardServices(config),
    CompleteOrder(config),
)
terminate = Pipeline(
    SetupContext(config),
    TerminateResponsibilityTransferStep(config),
    TerminateFinOpsEntitlementStep(config),
    CRMTicketTerminateOrder(config),
    CompleteTerminationOrder(config),
)
