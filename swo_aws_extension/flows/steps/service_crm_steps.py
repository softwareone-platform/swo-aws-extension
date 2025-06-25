import logging
from collections.abc import Callable

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import (
    CRM_KEEPER_ADDITIONAL_INFO,
    CRM_KEEPER_SUMMARY,
    CRM_KEEPER_TITLE,
    CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
    CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_ADDITIONAL_INFO,
    CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_SUMMARY,
    CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_TITLE,
    CRM_NEW_ACCOUNT_SUMMARY,
    CRM_NEW_ACCOUNT_TITLE,
    CRM_TERMINATION_ADDITIONAL_INFO,
    CRM_TERMINATION_SUMMARY,
    CRM_TERMINATION_TITLE,
    CRM_TICKET_RESOLVED_STATE,
    CRM_TRANSFER_WITH_ORGANIZATION_ADDITIONAL_INFO,
    CRM_TRANSFER_WITH_ORGANIZATION_SUMMARY,
    CRM_TRANSFER_WITH_ORGANIZATION_TITLE,
    OrderProcessingTemplateEnum,
)
from swo_aws_extension.flows.order import (
    InitialAWSContext,
    PurchaseContext,
)
from swo_aws_extension.parameters import (
    get_crm_ccp_ticket_id,
    get_crm_keeper_ticket_id,
    get_crm_onboard_ticket_id,
    get_crm_termination_ticket_id,
    get_crm_transfer_organization_ticket_id,
    get_master_payer_id,
    set_crm_keeper_ticket_id,
    set_crm_onboard_ticket_id,
    set_crm_termination_ticket_id,
    set_crm_transfer_organization_ticket_id,
)
from swo_crm_service_client import ServiceRequest
from swo_crm_service_client.client import get_service_client

logger = logging.getLogger(__name__)


class AwaitCRMTicketStatusStep(Step):
    def __init__(
        self,
        get_ticket_id: callable(InitialAWSContext),
        target_status=None,
        skip_if_no_ticket=True,
    ):
        """
        Await for a CRM ticket to reach any of the target status before proceeding.
        :param get_ticket_id: Callable[[CloseAccountContext], str|None] - Get ticket ID from context
        :param target_status: Optional[str | List[str]]
            Example: ["Completed", "Closed"] Default: [CRM_TICKET_RESOLVED_STATE]
        :param skip_if_no_ticket: bool - Skip if no ticket ID is found

        :raise ValueError: If ticket ID is required and not found
        """
        self.get_ticket_id = get_ticket_id
        target_status = target_status or [CRM_TICKET_RESOLVED_STATE]
        if not isinstance(target_status, list):
            target_status = [target_status]
        self.target_status = target_status
        self.skip_if_no_ticket = skip_if_no_ticket

    def __call__(
        self,
        client: MPTClient,
        context: InitialAWSContext,
        next_step: NextStep,
    ) -> None:
        ticket_id = self.get_ticket_id(context)
        if not ticket_id and not self.skip_if_no_ticket:
            raise ValueError("Ticket ID is required.")
        if not ticket_id:
            next_step(client, context)
            return
        crm_service_client = get_service_client()
        ticket = crm_service_client.get_service_requests(context.order_id, ticket_id)
        if ticket["state"] not in self.target_status:
            logger.info(
                f"{context.order_id} - Stopping - Awaiting for ticket_id={ticket_id} "
                f"to move from state={ticket['state']} to any of {self.target_status}"
            )
            return
        next_step(client, context)


class CreateServiceRequestStep(Step):
    def __init__(
        self,
        service_request_factory: Callable[[InitialAWSContext], ServiceRequest],
        ticket_id_saver: Callable[[MPTClient, InitialAWSContext, str], None],
        criteria: Callable[[InitialAWSContext], bool] = None,
    ):
        self.service_request_factory = service_request_factory
        self.ticket_id_saver = ticket_id_saver
        self.criteria = criteria or (lambda context: True)

    def meets_criteria(self, context):
        return self.criteria(context)

    def __call__(
        self,
        client: MPTClient,
        context,
        next_step: NextStep,
    ) -> None:
        if not self.meets_criteria(context):
            logger.info(
                f"{context.order_id} - Skipping - Criteria not met to Create a Service ticket."
            )
            next_step(client, context)
            return
        service_request = self.service_request_factory(context)
        crm_client = get_service_client()
        response = crm_client.create_service_request(context.order_id, service_request)
        ticket_id = response.get("id", None)
        self.ticket_id_saver(client, context, ticket_id)
        next_step(client, context)


class CreateTerminationServiceRequestStep(CreateServiceRequestStep):
    @staticmethod
    def should_create_ticket_criteria(context: InitialAWSContext) -> bool:
        """
        :param context:
        :return:
        """
        return not get_crm_termination_ticket_id(context.order)

    @staticmethod
    def build_service_request(context) -> ServiceRequest:
        if not context.mpa_account:
            raise RuntimeError(
                "Unable to create a service request ticket for an order missing an "
                "MPA account in the fulfillment parameters"
            )

        accounts = ", ".join(context.terminating_subscriptions_aws_account_ids)
        summary = CRM_TERMINATION_SUMMARY.format(
            accounts=accounts,
            termination_type=context.termination_type,
            mpa_account=context.mpa_account,
            order_id=context.order_id,
        )

        return ServiceRequest(
            additional_info=CRM_TERMINATION_ADDITIONAL_INFO,
            title=CRM_TERMINATION_TITLE.format(mpa_account=context.mpa_account),
            summary=summary,
        )

    @staticmethod
    def save_ticket(client, context, crm_ticket_id):
        if not crm_ticket_id:
            raise ValueError("Updating crm service ticket id - Ticket id is required.")
        logger.info(
            f"{context.order_id} - Action - Ticket created for terminate account "
            f"with id={crm_ticket_id}"
        )
        context.order = set_crm_termination_ticket_id(context.order, crm_ticket_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])

    def __init__(self):
        super().__init__(
            service_request_factory=self.build_service_request,
            ticket_id_saver=self.save_ticket,
            criteria=self.should_create_ticket_criteria,
        )


class AwaitTerminationServiceRequestStep(AwaitCRMTicketStatusStep):
    @staticmethod
    def get_crm_ticket(context: InitialAWSContext):
        return get_crm_termination_ticket_id(context.order)

    def __init__(self):
        super().__init__(
            get_ticket_id=self.get_crm_ticket,
            target_status=CRM_TICKET_RESOLVED_STATE,
            skip_if_no_ticket=True,
        )


class CreateTransferRequestTicketWithOrganizationStep(CreateServiceRequestStep):
    @staticmethod
    def build_service_request(context: PurchaseContext):
        email_address = context.buyer.get("contact", {}).get("email")
        master_payer_id = get_master_payer_id(context.order)
        if not master_payer_id:
            raise ValueError(
                f"Unable to create a transfer service request ticket for order={context.order_id}. "
                f"Reason: Missing master payer id."
            )

        return ServiceRequest(
            additional_info=CRM_TRANSFER_WITH_ORGANIZATION_ADDITIONAL_INFO,
            title=CRM_TRANSFER_WITH_ORGANIZATION_TITLE.format(
                master_payer_id=master_payer_id, email_address=email_address
            ),
            summary=CRM_TRANSFER_WITH_ORGANIZATION_SUMMARY.format(
                master_payer_id=master_payer_id,
                email_address=email_address,
                order_id=context.order_id,
            ),
        )

    @staticmethod
    def save_ticket(client, context, crm_ticket_id):
        if not crm_ticket_id:
            raise ValueError("Updating crm service ticket id - Ticket id is required.")
        logger.info(
            f"{context.order_id} - Action - Ticket created for transfer organization "
            f"with id={crm_ticket_id}"
        )
        context.order = set_crm_transfer_organization_ticket_id(context.order, crm_ticket_id)
        context.update_processing_template(
            client,
            OrderProcessingTemplateEnum.TRANSFER_WITH_ORG_TICKET_CREATED,
        )
        logger.info(
            f"{context.order_id} - Action - Created transfer service request ticket with "
            f"id={crm_ticket_id}"
        )

    @staticmethod
    def should_create_ticket_criteria(context):
        """
        :param context:
        :return:
        """
        has_ticket = bool(get_crm_transfer_organization_ticket_id(context.order))
        return not has_ticket and context.is_type_transfer_with_organization()

    def __init__(self):
        super().__init__(
            service_request_factory=self.build_service_request,
            ticket_id_saver=self.save_ticket,
            criteria=self.should_create_ticket_criteria,
        )


class CreateUpdateKeeperTicketStep(CreateServiceRequestStep):
    @staticmethod
    def should_create_ticket_criteria(context: InitialAWSContext) -> bool:
        """
        :param context:
        :return:
        """
        return not get_crm_keeper_ticket_id(context.order)

    @staticmethod
    def build_service_request(context: PurchaseContext) -> ServiceRequest:
        if not context.airtable_mpa:
            raise RuntimeError(
                "Unable to create a service request ticket for an order missing airtable_mpa"
            )

        return ServiceRequest(
            additional_info=CRM_KEEPER_ADDITIONAL_INFO,
            title=CRM_KEEPER_TITLE.format(
                mpa_account=context.mpa_account, scu=context.airtable_mpa.scu
            ),
            summary=CRM_KEEPER_SUMMARY.format(
                account_id=context.mpa_account,
                account_name=context.airtable_mpa.account_name,
                account_email=context.airtable_mpa.account_email,
                pls_enabled=context.airtable_mpa.pls_enabled,
                scu=context.airtable_mpa.scu,
                buyer_id=context.airtable_mpa.buyer_id,
                order_id=context.order_id,
            ),
        )

    @staticmethod
    def save_ticket(client, context, crm_ticket_id):
        if not crm_ticket_id:
            raise ValueError("Ticket id is required.")
        logger.info(
            f"{context.order_id} - Action - Ticket created for keeper shared credentials "
            f"with id={crm_ticket_id}"
        )
        context.order = set_crm_keeper_ticket_id(context.order, crm_ticket_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])

    def __init__(self):
        super().__init__(
            service_request_factory=self.build_service_request,
            ticket_id_saver=self.save_ticket,
            criteria=self.should_create_ticket_criteria,
        )


class CreateOnboardTicketStep(CreateServiceRequestStep):
    @staticmethod
    def should_create_ticket_criteria(context: InitialAWSContext) -> bool:
        """
        :param context:
        :return:
        """
        return not get_crm_onboard_ticket_id(context.order)

    @staticmethod
    def build_service_request(context: PurchaseContext) -> ServiceRequest:
        if not context.airtable_mpa:
            raise RuntimeError(
                "Unable to create a service request ticket for an order missing airtable_mpa"
            )
        ccp_ticket_id = get_crm_ccp_ticket_id(context.order)
        if ccp_ticket_id:
            title = CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_TITLE
            additional_info = CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_ADDITIONAL_INFO
            summary = CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_SUMMARY.format(
                customer_name=context.airtable_mpa.account_name,
                buyer_external_id=context.airtable_mpa.buyer_id,
                order_id=context.order_id,
                master_payer_id=context.mpa_account,
                automation_ticket_id=ccp_ticket_id,
            )
        else:
            title = CRM_NEW_ACCOUNT_TITLE
            additional_info = CRM_NEW_ACCOUNT_ADDITIONAL_INFO
            summary = CRM_NEW_ACCOUNT_SUMMARY.format(
                customer_name=context.airtable_mpa.account_name,
                buyer_external_id=context.airtable_mpa.buyer_id,
                order_id=context.order_id,
                master_payer_id=context.mpa_account,
            )
        return ServiceRequest(additional_info=additional_info, title=title, summary=summary)

    @staticmethod
    def save_ticket(client, context, crm_ticket_id):
        if not crm_ticket_id:
            raise ValueError("Ticket id is required.")
        logger.info(
            f"{context.order_id} - Action - Ticket created for onboard account "
            f"with id={crm_ticket_id}"
        )
        context.order = set_crm_onboard_ticket_id(context.order, crm_ticket_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])

    def __init__(self):
        super().__init__(
            service_request_factory=self.build_service_request,
            ticket_id_saver=self.save_ticket,
            criteria=self.should_create_ticket_criteria,
        )


class AwaitTransferRequestTicketWithOrganizationStep(AwaitCRMTicketStatusStep):
    @staticmethod
    def get_crm_ticket(context: InitialAWSContext):
        return get_crm_transfer_organization_ticket_id(context.order)

    def __init__(self):
        super().__init__(
            get_ticket_id=self.get_crm_ticket,
            target_status=CRM_TICKET_RESOLVED_STATE,
            skip_if_no_ticket=True,
        )
