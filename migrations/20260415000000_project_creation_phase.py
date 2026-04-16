import logging
import os

from mpt_api_client.rql.query_builder import RQLQuery
from mpt_tool.migration import DataBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

logger = logging.getLogger(__name__)

_phases_options = {
    "options": {
        "placeholderText": "Fulfillment phase",
        "description": "Fulfillment phase",
        "optionsList": [
            {"label": "Create Account", "value": "createAccount"},
            {
                "label": "Create Billing Transfer Invitation",
                "value": "createBillingTransferInvitation",
            },
            {
                "label": "Check Billing Transfer Invitation",
                "value": "checkBillingTransferInvitation",
            },
            {"label": "Configure APN Program", "value": "configureApnProgram"},
            {"label": "Create Channel Handshake", "value": "createChannelHandshake"},
            {
                "label": "Check Channel Handshake status",
                "value": "checkChannelHandshakeStatus",
            },
            {"label": "Check Customer Roles", "value": "checkCustomerRoles"},
            {"label": "Onboard Services", "value": "onboardServices"},
            {"label": "Check Onboard Status", "value": "checkOnboardStatus"},
            {"label": "Project Creation", "value": "projectCreation"},
            {"label": "Create Subscriptions", "value": "createSubscription"},
            {"label": "Completed", "value": "completed"},
        ],
        "hintText": "Fulfillment phase",
    }
}

_cco_contract_number_parameter = {
    "name": "CCO Contract Number",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "CCO Contract Number",
    "multiple": False,
    "externalId": "ccoContractNumber",
    "displayOrder": 110,
    "constraints": {"hidden": False, "readonly": False, "required": False},
    "options": {
        "placeholderText": "CCO Contract Number",
        "hintText": "CCO Contract Number",
    },
    "type": "SingleLineText",
    "status": "Active",
}

_erp_project_no_parameter = {
    "name": "Service Provisioning Project (SWO Job)",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Service Provisioning Project (SWO Job)",
    "multiple": False,
    "externalId": "erpProjectNo",
    "displayOrder": 120,
    "constraints": {"hidden": False, "readonly": False, "required": False},
    "options": {
        "placeholderText": "Service Provisioning Project (SWO Job)",
        "hintText": "Service Provisioning Project (SWO Job)",
    },
    "type": "SingleLineText",
    "status": "Active",
}


class Migration(DataBaseMigration, MPTAPIClientMixin):
    """Migration to add PROJECT_CREATION phase and ccoContractNumber / erpProjectNo parameters."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        logger.info(
            "Starting migration 20260415000000_project_creation_phase for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            logger.info("No product IDs found in MPT_PRODUCTS_IDS; nothing to migrate")

        for product_id in product_ids:
            self._migrate_product(product_id)

        logger.info("Migration 20260415000000_project_creation_phase finished")

    def _migrate_product(self, product_id: str) -> None:
        logger.info("Migrating product '%s'", product_id)

        cco_contract_parameter = self._get_product_parameter(product_id, "ccoContractNumber")
        erp_project_parameter = self._get_product_parameter(product_id, "erpProjectNo")

        self._update_product_phases(product_id)
        self._ensure_parameter(
            product_id,
            cco_contract_parameter,
            _cco_contract_number_parameter,
        )
        self._ensure_parameter(
            product_id,
            erp_project_parameter,
            _erp_project_no_parameter,
        )

    def _ensure_parameter(
        self,
        product_id: str,
        existing_parameter,
        parameter_data: dict,
    ) -> None:
        external_id = parameter_data["externalId"]
        if existing_parameter:
            logger.info(
                "Parameter '%s' already exists for product '%s'; skipping",
                external_id,
                product_id,
            )
            return

        logger.info("Creating parameter '%s' for product '%s'", external_id, product_id)
        self._create_product_parameter(product_id, parameter_data)

    def _get_product_parameter(self, product_id: str, external_id: str) -> str | None:
        product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
        parameter_query = RQLQuery(externalId=external_id)
        status_query = RQLQuery(status="Active")
        product_parameters = list(
            product_parameters_service
            .filter(parameter_query)
            .filter(status_query)
            .select()
            .iterate()
        )
        if product_parameters:
            return product_parameters[0]
        return None

    def _update_product_phases(self, product_id: str):
        phase_parameter = self._get_product_parameter(product_id, "phase")
        if phase_parameter:
            logger.info("Updating 'phase' parameter options for product '%s'", product_id)
            product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
            product_parameters_service.update(phase_parameter.id, _phases_options)
        else:
            logger.info("No 'phase' parameter found for product '%s'; skipping update", product_id)

    def _create_product_parameter(self, product_id: str, parameter_data: dict):
        logger.info(
            "Creating product parameter '%s' for product '%s'",
            parameter_data.get("externalId"),
            product_id,
        )
        product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
        product_parameters_service.create(parameter_data)
