import logging
import os
from collections.abc import Mapping
from typing import Any

from mpt_api_client.rql.query_builder import RQLQuery
from mpt_tool.migration import SchemaBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

logger = logging.getLogger(__name__)

_MIGRATION_EXTERNAL_ID = "is_migration"
_MIGRATION_YES = "yes"
_MIGRATION_NO = "no"
_CRM_MIGRATION_TICKET_ID_EXTERNAL_ID = "crmMigrationTicketId"
_AWS_DETAILS_GROUP_NAME = "AWS Details"


def _get_parameter_group_by_name(mpt_client, product_id: str, group_name: str) -> Any | None:
    parameter_groups_service = mpt_client.catalog.products.parameter_groups(product_id)
    group_query = RQLQuery(name=group_name)
    found = list(parameter_groups_service.filter(group_query).select().iterate())
    return found[0] if found else None


_migration_parameter = {
    "name": "Migration",
    "scope": "Agreement",
    "phase": "Order",
    "context": "None",
    "description": (
        "Marks the order as an AWS migration order created by SoftwareOne on behalf of the customer"
    ),
    "multiple": False,
    "externalId": _MIGRATION_EXTERNAL_ID,
    "displayOrder": 100,
    "constraints": {"hidden": True, "readonly": False, "required": False},
    "options": {
        "optionsList": [
            {
                "label": "Yes",
                "value": _MIGRATION_YES,
                "description": "The order migrates an existing SoftwareOne resold AWS customer",
            },
            {
                "label": "No",
                "value": _MIGRATION_NO,
                "description": "Regular order",
            },
        ],
        "defaultValue": _MIGRATION_NO,
        "hintText": "Migration",
    },
    "type": "Choice",
    "status": "Active",
}

_crm_migration_ticket_id_parameter = {
    "name": "Migration ticket ID",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "ServiceNow ticket ID created for the migrated customer",
    "multiple": False,
    "externalId": _CRM_MIGRATION_TICKET_ID_EXTERNAL_ID,
    "displayOrder": 150,
    "constraints": {"hidden": True, "readonly": False, "required": False},
    "options": {
        "placeholderText": "Migration ticket ID",
        "hintText": "Migration ticket ID",
    },
    "type": "SingleLineText",
    "status": "Active",
}


class Migration(SchemaBaseMigration, MPTAPIClientMixin):
    """Migration to add the migration ordering parameter and the crmMigrationTicketId parameter."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        logger.info(
            "Starting migration 20260903144831_migration for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            logger.info("No product IDs found in MPT_PRODUCTS_IDS; nothing to migrate")

        for product_id in product_ids:
            self._migrate_product(product_id)

        logger.info("Migration 20260903144831_migration finished")

    def _migrate_product(self, product_id: str) -> None:
        logger.info("Migrating product '%s'", product_id)

        aws_details_group = _get_parameter_group_by_name(
            self.mpt_client, product_id, _AWS_DETAILS_GROUP_NAME
        )
        if aws_details_group is None:
            raise RuntimeError(
                f"Parameter group '{_AWS_DETAILS_GROUP_NAME}' does not exist for product "
                f"'{product_id}'. Create the group in the platform before running this migration."
            )

        migration_parameter = {**_migration_parameter, "group": {"id": aws_details_group.id}}
        existing_migration = self._get_product_parameter(product_id, _MIGRATION_EXTERNAL_ID)
        self._ensure_parameter(product_id, existing_migration, migration_parameter)

        existing_ticket_id = self._get_product_parameter(
            product_id, _CRM_MIGRATION_TICKET_ID_EXTERNAL_ID
        )
        self._ensure_parameter(product_id, existing_ticket_id, _crm_migration_ticket_id_parameter)

    def _ensure_parameter(
        self,
        product_id: str,
        existing_parameter: Any | None,
        parameter_data: Mapping[str, Any],
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

    def _get_product_parameter(self, product_id: str, external_id: str) -> Any | None:
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

    def _create_product_parameter(self, product_id: str, parameter_data: Mapping[str, Any]) -> None:
        logger.info(
            "Creating product parameter '%s' for product '%s'",
            parameter_data.get("externalId"),
            product_id,
        )
        product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
        product_parameters_service.create(parameter_data)
