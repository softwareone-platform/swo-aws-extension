import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order
from requests import HTTPError

from swo_aws_extension.airtable.models import get_mpa_account
from swo_aws_extension.constants import (
    CRM_CCP_TICKET_ADDITIONAL_INFO,
    CRM_CCP_TICKET_SUMMARY,
    CRM_CCP_TICKET_TITLE,
    CCPOnboardStatusEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.notifications import send_error
from swo_aws_extension.parameters import (
    get_crm_ccp_ticket_id,
    get_phase,
    set_ccp_engagement_id,
    set_crm_ccp_ticket_id,
    set_phase,
)
from swo_ccp_client.client import CCPClient
from swo_crm_service_client import ServiceRequest
from swo_crm_service_client.client import get_service_client

logger = logging.getLogger(__name__)


class CCPOnboard(Step):
    """Onboard account for CCP."""
    def __init__(self, config):
        self.config = config

    def __call__(self, mpt_client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        if get_phase(context.order) != PhasesEnum.CCP_ONBOARD:
            logger.info(
                "Current phase is '%s', skipping as it is not '%s'",
                get_phase(context.order), PhasesEnum.CCP_ONBOARD.value,
            )
            next_step(mpt_client, context)
            return
        try:
            ccp_client = CCPClient(self.config)

            if context.ccp_engagement_id:
                self._check_onboarding_status(mpt_client, ccp_client, context, next_step)
            else:
                self._onboard_customer(mpt_client, ccp_client, context)
        except HTTPError as e:
            logger.exception("HTTP error occurred: CCP Error.")
            title = f"CCP onboard failed: {context.ccp_engagement_id} "
            message = (
                f"CCP onboard for order {context.order_id} with engagement id"
                f" {context.ccp_engagement_id} is failing with error: {e}"
            )
            send_error(title, message)

    def _check_onboarding_status(self, mpt_client, ccp_client, context, next_step):
        """
        Check the onboarding status of the customer.

        Args:
            mpt_client: MPT client instance.
            ccp_client: CCP client instance.
            context: PurchaseContext object containing order details.
            next_step: Function to call for the next step in the pipeline.

        """
        logger.info(
            "%s - Action - Checking CCP onboarding status for ccp_engagement_id=%s",
            context.order_id, context.ccp_engagement_id,
        )

        onboard_status = ccp_client.get_onboard_status(context.ccp_engagement_id)
        logger.info("CCP Onboarding status: %s", onboard_status)

        if onboard_status["engagementState"] == CCPOnboardStatusEnum.RUNNING:
            logger.info("%s - Stop - CCP Onboarding is still in progress.", context.order_id)
            return
        if onboard_status["engagementState"] == CCPOnboardStatusEnum.SUCCEEDED:
            context.order = set_phase(context.order, PhasesEnum.COMPLETED.value)
            context.order = update_order(
                mpt_client, context.order_id, parameters=context.order["parameters"]
            )

            logger.info("%s - Next - CCP Onboarding completed successfully.", context.order_id)
            next_step(mpt_client, context)
            return
        logger.info(
            "%s - CCP Onboarding is in status %s. Notify the failure and continue",
            context.order_id, onboard_status["engagementState"],
        )
        self._notify_ccp_onboard_failure(context, onboard_status)
        context.order = set_phase(context.order, PhasesEnum.COMPLETED.value)
        context.order = update_order(
            mpt_client, context.order_id, parameters=context.order["parameters"]
        )
        next_step(mpt_client, context)

    def _onboard_customer(self, mpt_client, ccp_client, context):
        """
        Onboard a customer using the CCP API.

        Args:
            mpt_client: MPT client instance.
            ccp_client: CCP client instance.
            context: PurchaseContext object containing order details.
        """
        logger.info("Starting CCP onboarding")

        mpa_account = get_mpa_account(context.mpa_account)
        customer = {
            "customerName": mpa_account.account_name,
            "customerSCU": mpa_account.scu,
            "accountId": context.mpa_account,
            "services": {
                "isManaged": True,
                "isSamlEnabled": True,
                "isBillingEnabled": True,
            },
            "featurePLS": ("enabled" if mpa_account.pls_enabled else "disabled"),
        }
        response = ccp_client.onboard_customer(customer)
        engagement = next(iter(filter(lambda x: "engagement" in x, response)))

        logger.info("CCP Onboarding engagement: %s", engagement.get("id", ""))

        context.order = set_ccp_engagement_id(context.order, engagement.get("id", ""))
        context.order = update_order(
            mpt_client, context.order_id, parameters=context.order["parameters"]
        )

        logger.info("- Action - CCP Customer created. Waiting for onboarding")

    def _notify_ccp_onboard_failure(self, context, onboard_status):
        """
        Create a fail ticket notification.

        Args:
            context: PurchaseContext object containing order details.
            onboard_status: CCP onboard status.
        """
        ccp_ticket_id = get_crm_ccp_ticket_id(context.order)
        if ccp_ticket_id:
            logger.info("CCP Onboard failure ticket already created (%s). Skip.", ccp_ticket_id)
            return

        crm_client = get_service_client()
        title = CRM_CCP_TICKET_TITLE.format(ccp_engagement_id=context.ccp_engagement_id)
        summary = CRM_CCP_TICKET_SUMMARY.format(
            ccp_engagement_id=context.ccp_engagement_id,
            order_id=context.order_id,
            onboard_status=onboard_status,
        )
        service_request = ServiceRequest(
            additional_info=CRM_CCP_TICKET_ADDITIONAL_INFO,
            summary=summary,
            title=title,
            service_type="MarketPlaceAutomation",
        )
        ticket = crm_client.create_service_request(context.order_id, service_request)
        context.order = set_crm_ccp_ticket_id(context.order, ticket.get("id", ""))
        logger.info(
            "Service request ticket created with id: %s. Continue purchase", ticket.get("id", "")
        )
        send_error(title, summary)
