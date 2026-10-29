import logging
import os
from typing import Any

from mpt_api_client.rql.query_builder import RQLQuery
from mpt_tool.migration import SchemaBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

logger = logging.getLogger(__name__)

_MASTER_PAYER_ID_EXTERNAL_ID = "masterPayerID"


class Migration(SchemaBaseMigration, MPTAPIClientMixin):
    """Migration to make the masterPayerID product parameter visible."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        logger.info(
            "Starting migration 20261029125642_master_payer_id_visible for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            logger.info("No product IDs found in MPT_PRODUCTS_IDS; nothing to migrate")

        for product_id in product_ids:
            self._migrate_product(product_id)

    def _migrate_product(self, product_id: str) -> None:
        logger.info("Migrating product '%s'", product_id)
        parameter = self._get_product_parameter(product_id, _MASTER_PAYER_ID_EXTERNAL_ID)
        if not parameter:
            logger.info(
                "No '%s' parameter found for product '%s'; skipping",
                _MASTER_PAYER_ID_EXTERNAL_ID,
                product_id,
            )
            return

        constraints = parameter.constraints.to_dict()
        if not constraints.get("hidden"):
            logger.info(
                "Parameter '%s' is already visible for product '%s'; skipping",
                _MASTER_PAYER_ID_EXTERNAL_ID,
                product_id,
            )
            return

        logger.info(
            "Making parameter '%s' visible for product '%s'",
            _MASTER_PAYER_ID_EXTERNAL_ID,
            product_id,
        )
        product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
        product_parameters_service.update(
            parameter.id,
            {"constraints": {**constraints, "hidden": False}},
        )

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
