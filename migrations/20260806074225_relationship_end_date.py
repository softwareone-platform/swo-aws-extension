import logging
import os
from collections.abc import Mapping
from typing import Any

from mpt_api_client.rql.query_builder import RQLQuery
from mpt_tool.migration import SchemaBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

logger = logging.getLogger(__name__)

_RELATIONSHIP_END_DATE_EXTERNAL_ID = "relationshipEndDate"

_relationship_end_date_parameter = {
    "name": "Relationship End Date",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Date when the AWS responsibility transfer relationship ends",
    "multiple": False,
    "externalId": _RELATIONSHIP_END_DATE_EXTERNAL_ID,
    "displayOrder": 140,
    "constraints": {"hidden": True, "readonly": False, "required": False},
    "options": {
        "placeholderText": "Relationship End Date",
        "hintText": "Relationship End Date",
    },
    "type": "SingleLineText",
    "status": "Active",
}


class Migration(SchemaBaseMigration, MPTAPIClientMixin):
    """Migration to add the relationshipEndDate agreement fulfillment parameter."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        logger.info(
            "Starting migration 20260806074225_relationship_end_date for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            logger.info("No product IDs found in MPT_PRODUCTS_IDS; nothing to migrate")

        for product_id in product_ids:
            self._migrate_product(product_id)

        logger.info("Migration 20260806074225_relationship_end_date finished")

    def _migrate_product(self, product_id: str) -> None:
        logger.info("Migrating product '%s'", product_id)

        existing = self._get_product_parameter(product_id, _RELATIONSHIP_END_DATE_EXTERNAL_ID)
        self._ensure_parameter(product_id, existing, _relationship_end_date_parameter)
        self._migrate_agreements(product_id)

    def _migrate_agreements(self, product_id: str) -> None:
        logger.info("Migrating agreements for product '%s'", product_id)
        query = RQLQuery(product__id=product_id) & RQLQuery(status="Active")
        agreements = list(
            self.mpt_client.commerce.agreements.filter(query).select("+parameters").iterate()
        )
        logger.info(
            "Found %s active agreement(s) for product '%s'",
            len(agreements),
            product_id,
        )
        for agreement in agreements:
            self._ensure_agreement_relationship_end_date(agreement.to_dict())

    def _ensure_agreement_relationship_end_date(self, agreement: dict[str, Any]) -> None:
        agreement_id = agreement["id"]
        fulfillment_params = agreement.get("parameters", {}).get("fulfillment", [])
        already_present = any(
            parameter.get("externalId") == _RELATIONSHIP_END_DATE_EXTERNAL_ID
            for parameter in fulfillment_params
        )
        if already_present:
            logger.info(
                "Parameter 'relationshipEndDate' already exists for agreement '%s'; skipping",
                agreement_id,
            )
            return
        logger.info("Adding parameter 'relationshipEndDate' to agreement '%s'", agreement_id)
        self.mpt_client.commerce.agreements.update(
            agreement_id,
            {
                "parameters": {
                    "fulfillment": [
                        {
                            "externalId": _RELATIONSHIP_END_DATE_EXTERNAL_ID,
                            "value": "",
                        }
                    ]
                }
            },
        )

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
