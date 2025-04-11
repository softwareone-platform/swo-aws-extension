import logging

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.airtable.models import (
    MPAStatusEnum,
    get_mpa_view_link,
)
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import (
    PurchaseContext,
)
from swo_aws_extension.notifications import Button, send_error
from swo_aws_extension.parameters import get_phase, set_mpa_account_id, set_phase

logger = logging.getLogger(__name__)


class AssignMPA(Step):
    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        phase = get_phase(context.order)
        if phase and phase != PhasesEnum.ASSIGN_MPA:
            logger.info(
                f"- Next - Current phase is '{phase}', "
                f"skipping as it is not '{PhasesEnum.ASSIGN_MPA}'"
            )
            next_step(client, context)
            return

        if context.mpa_account:
            context.order = set_phase(context.order, PhasesEnum.PRECONFIGURATION_MPA)
            context.order = update_order(
                client, context.order_id, parameters=context.order["parameters"]
            )
            logger.info(
                f"- Next - MPA account {context.mpa_account} "
                f"already assigned to order {context.order_id}. Continue"
            )
            next_step(client, context)
            return

        if not context.airtable_mpa:
            logger.error(
                "No MPA available in the pool with PLS "
                + ("enabled" if context.pls_enabled else "disabled")
            )
            return

        # validate mpa_id
        are_credentials_valid = True
        credentials_error = ""
        try:
            context.aws_client = AWSClient(
                self._config, context.airtable_mpa.account_id, self._role_name
            )
            context.aws_client.get_caller_identity()
        except AWSError as e:
            logger.error(
                f"- Error- Failed to retrieve MPA credentials for "
                f"{context.airtable_mpa.account_id}: {e}"
            )
            are_credentials_valid = False
            credentials_error = str(e)

        if not are_credentials_valid:
            context.airtable_mpa.status = MPAStatusEnum.ERROR
            context.airtable_mpa.error_description = str(credentials_error)
            context.airtable_mpa.save()
            mpa_view_link = get_mpa_view_link()
            send_error(
                f"Master Payer account {context.airtable_mpa.account_id} "
                f"failed to retrieve credentials",
                f"The Master Payer Account {context.airtable_mpa.account_id} is "
                f"failing with error: {credentials_error}",
                button=Button("Open Master Payer Accounts View", mpa_view_link),
            )
            return
        logger.info(
            f"- Action - MPA credentials for {context.airtable_mpa.account_id} "
            f"retrieved successfully"
        )

        context.airtable_mpa.status = MPAStatusEnum.ASSIGNED
        context.airtable_mpa.agreement_id = context.order.get("agreement", {}).get("id")
        scu = context.order.get("buyer", {}).get("externalId", {}).get("erpCustomer", "")
        context.airtable_mpa.scu = scu
        context.airtable_mpa.buyer_id = context.order.get("buyer", {}).get("id", {})
        context.airtable_mpa.client_id = context.order.get("client", {}).get("id")
        context.airtable_mpa.error_description = ""
        context.airtable_mpa.save()
        context.order = set_mpa_account_id(context.order, context.airtable_mpa.account_id)

        context.order = set_phase(context.order, PhasesEnum.PRECONFIGURATION_MPA)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

        logger.info(f"- Next - Master Payer Account {context.mpa_account} assigned.")
        next_step(client, context)


class AssignTransferMPAStep(Step):
    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def setup_aws(self, context: PurchaseContext):
        context.aws_client = AWSClient(self._config, context.mpa_account, self._role_name)

    def validate_mpa_credentials(self, context: PurchaseContext):
        if not context.aws_client:
            raise RuntimeError("AssignTransferMPAStep - AWS client is not set in context")
        context.aws_client.describe_organization()

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step: NextStep):
        """
        If is a transfer account in phase ASSIGN_MPA:
        - Copy the master payer id to fulfillment mpa account id
        - Check access to the account
        - Set the phase to CREATE_SUBSCRIPTIONS
        """
        is_transfer_with_organization = (
            context.is_type_transfer_with_organization() and context.is_purchase_order()
        )
        if not is_transfer_with_organization:
            logger.info(f"{context.order_id} - Skipping - It is not a transfer with organization")
            next_step(client, context)
            return

        if get_phase(context.order) != PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION:
            logger.info(
                f"{context.order_id} - Skipping - Current phase is '{get_phase(context.order)}',"
                f" skipping as it is not '{PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION}'"
            )
            next_step(client, context)
            return

        if not context.mpa_account:
            logger.info(
                f"{context.order_id} - Action - MPA account is not set in context. "
                f"Setting to {context.order_master_payer_id}"
            )
            context.order = set_mpa_account_id(
                context.order,
                context.order_master_payer_id,
            )
            update_order(client, context.order_id, parameters=context.order["parameters"])
            logger.info(
                f"{context.order_id} - Action - Order updated with MPA account "
                f"`{context.mpa_account}`. "
            )

        try:
            if not context.aws_client:
                self.setup_aws(context)
            self.validate_mpa_credentials(context)
            context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS)
            logger.info(
                f"{context.order_id} - Action - Update phase to {PhasesEnum.CREATE_SUBSCRIPTIONS}"
            )
            update_order(client, context.order_id, parameters=context.order["parameters"])
            logger.info(
                f"{context.order_id} - Next - Validated Linked MPA account done."
                f" Proceeding to next step"
            )
            next_step(client, context)
        except AWSError as e:
            logger.exception(
                f"- Error- Failed to retrieve MPA credentials for {context.mpa_account}: {e}"
            )
            credentials_error = str(e)
            title = (
                f"Transfer with Organization MPA: {context.mpa_account} "
                f"failed to retrieve credentials."
            )
            message = (
                f"The transfer with organization Master Payer Account {context.mpa_account} is "
                f"failing with error: {credentials_error}"
            )
            send_error(title, message)
            return
