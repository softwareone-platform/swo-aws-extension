from swo.mpt.extensions.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    CRM_TICKET_COMPLETED_STATE,
    SWO_EXTENSION_MANAGEMENT_ROLE,
)
from swo_aws_extension.flows.fulfillment.close_account.last_account_ticket import (
    build_service_request_for_close_account,
    create_ticket_on_close_account_criteria,
    crm_ticket_id_saver,
    get_crm_ticket_id,
)
from swo_aws_extension.flows.steps import (
    AwaitCRMTicketStatusStep,
    CloseAWSAccountStep,
    CompleteOrder,
    CreateServiceRequestStep,
    SetupContext,
)

config = Config()

close_account_pipeline = Pipeline(
SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CloseAWSAccountStep(),
    CreateServiceRequestStep(
        build_service_request_for_close_account,
        crm_ticket_id_saver,
        create_ticket_on_close_account_criteria,
    ),
    AwaitCRMTicketStatusStep(
        lambda context: get_crm_ticket_id(context.order),
        CRM_TICKET_COMPLETED_STATE
    ),
    CompleteOrder("purchase_order")
)
