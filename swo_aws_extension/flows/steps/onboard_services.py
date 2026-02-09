import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (  # noqa: WPS235
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_phase,
    get_support_type,
    set_phase,
)
from swo_aws_extension.swo.notifications.email import EmailNotificationManager
from swo_aws_extension.swo.notifications.templates.deploy_services_feature import (
    DEPLOY_SERVICES_FEATURE_TEMPLATE,
)

logger = logging.getLogger(__name__)


class OnboardServices(BasePhaseStep):
    """Onboard Services step."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.ONBOARD_SERVICES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.ONBOARD_SERVICES}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        logger.info("%s - Action - Onboarding services", context.order_id)
        recipients = self._config.deploy_services_feature_recipients
        subject = DEPLOY_SERVICES_FEATURE_TEMPLATE.subject
        contact = get_formatted_technical_contact(context.order)
        body = DEPLOY_SERVICES_FEATURE_TEMPLATE.body.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            pm_account_id=context.pm_account_id,
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
        )
        EmailNotificationManager(self._config).send_email(recipients, subject, body)
        logger.info("%s - Next - Onboarding services email sent", context.order_id)

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
