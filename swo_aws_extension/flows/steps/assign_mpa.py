import logging

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_agreement, update_order

from swo_aws_extension.airtable.models import (
    MPAStatusEnum,
    NotificationStatusEnum,
    NotificationTypeEnum,
    create_pool_notification,
    get_mpa_view_link,
    has_open_notification,
)
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import (
    PurchaseContext,
    switch_order_to_query,
)
from swo_aws_extension.flows.validation.purchase import is_split_billing_mpa_id_valid
from swo_aws_extension.notifications import Button, send_error
from swo_aws_extension.parameters import (
    get_phase,
    get_transfer_type,
    list_ordering_parameters_with_errors,
    set_ordering_parameters_to_readonly,
    set_phase,
)

logger = logging.getLogger(__name__)


def coppy_context_data_to_mpa_pool_model(context, airtable_mpa, status=None):
    if status is None:
        status = MPAStatusEnum.ASSIGNED
    scu = context.order.get("buyer", {}).get("externalId", {}).get("erpCustomer", "")
    airtable_mpa.status = status
    airtable_mpa.agreement_id = context.agreement_id
    airtable_mpa.scu = scu
    airtable_mpa.buyer_id = context.order.get("buyer", {}).get("id", {})
    airtable_mpa.client_id = context.order.get("client", {}).get("id")
    airtable_mpa.error_description = ""
    return airtable_mpa


def setup_agreement_external_id(client, context, account_id):
    context.order["agreement"] = update_agreement(
        client,
        context.order["agreement"]["id"],
        externalIds={"vendor": account_id},
    )
    logger.info(
        f"Updating agreement {context.order["agreement"]["id"]} external id to {account_id}"
    )


class AssignMPA(Step):
    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        phase = get_phase(context.order)
        if phase and phase != PhasesEnum.ASSIGN_MPA:
            logger.info(
                f"{context.order_id} - Next - Current phase is '{phase}', "
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
                f"{context.order_id} - Next - MPA account {context.mpa_account} "
                f"already assigned to order {context.order_id}. Continue"
            )
            next_step(client, context)
            return
        if get_transfer_type(context.order) == TransferTypesEnum.SPLIT_BILLING:
            if not is_split_billing_mpa_id_valid(context):
                parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
                context.order = set_ordering_parameters_to_readonly(
                    context.order, ignore=parameter_ids_with_errors
                )
                switch_order_to_query(client, context.order)
                logger.error(
                    f"{context.order_id} - Querying - MPA Invalid. Order switched to query"
                )
                return
            setup_agreement_external_id(client, context, context.order_master_payer_id)
            context.order = set_phase(context.order, PhasesEnum.PRECONFIGURATION_MPA)
            context.order = update_order(
                client, context.order_id, parameters=context.order["parameters"]
            )

            logger.info(
                f"{context.order_id} - Next - Split Billing Master Payer Account "
                f"{context.mpa_account} assigned."
            )
            next_step(client, context)

        if not context.airtable_mpa:
            logger.error(
                f"{context.order_id} - Error - No MPA available in the pool for country"
                f" {context.seller_country} with PLS enabled: {context.pls_enabled}"
            )
            if not has_open_notification(context.seller_country, context.pls_enabled):
                new_notification = {
                    "status": NotificationStatusEnum.NEW,
                    "notification_type": NotificationTypeEnum.EMPTY,
                    "pls_enabled": context.pls_enabled,
                    "country": context.seller_country,
                }
                create_pool_notification(new_notification)
                logger.info(
                    f"{context.order_id} - Action - Created new empty notification for "
                    f"{context.seller_country} with PLS status: {context.pls_enabled}"
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
                f"{context.order_id} - Error - Failed to retrieve MPA credentials for "
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
            f"{context.order_id} - Action - MPA credentials for {context.airtable_mpa.account_id} "
            f"retrieved successfully"
        )
        airtable_mpa = context.airtable_mpa
        airtable_mpa = coppy_context_data_to_mpa_pool_model(context, airtable_mpa)
        airtable_mpa.save()

        context.airtable_mpa = airtable_mpa
        setup_agreement_external_id(client, context, context.airtable_mpa.account_id)

        context.order = set_phase(context.order, PhasesEnum.PRECONFIGURATION_MPA)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

        logger.info(
            f"{context.order_id} - Next - Master Payer Account {context.mpa_account} assigned."
        )
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
            setup_agreement_external_id(client, context, context.order_master_payer_id)
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
                f"{context.order_id} - Error- Failed to retrieve MPA credentials for "
                f"{context.mpa_account}: {e}"
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
