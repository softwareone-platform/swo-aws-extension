import json
import logging
import os

from mpt_tool.migration import SchemaBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

logger = logging.getLogger(__name__)


class Migration(SchemaBaseMigration, MPTAPIClientMixin):
    """Migration to add terminationDate and splitBillingPolicy parameters for split billing."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        logger.info(
            "Starting migration 20260610073112_split_billing_per_linked_account for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            logger.info("No product IDs found in MPT_PRODUCTS_IDS; nothing to migrate")

        for product_id in product_ids:
            self._migrate_product(product_id)

        logger.info("Migration 20260610073112_split_billing_per_linked_account finished")

    def _migrate_product(self, product_id: str) -> None:
        logger.info("Migrating product '%s'", product_id)

        self._enable_termination_order_validation(product_id)
        self._create_termination_order_webhook(product_id)

    def _enable_termination_order_validation(self, product_id: str) -> None:
        product = self.mpt_client.catalog.products.get(product_id).to_dict()
        if product.get("settings", {}).get("preValidation", {}).get("terminationOrder"):
            logger.info(
                "Termination order draft validation already enabled for product '%s'; skipping",
                product_id,
            )
            return
        product["settings"]["preValidation"]["terminationOrder"] = True
        self.mpt_client.catalog.products.update_settings(product_id, product["settings"])
        logger.info("Enabled termination order draft validation for product '%s'", product_id)

    def _create_termination_order_webhook(self, product_id: str) -> None:
        webhooks = self.mpt_client.http_client.request(
            "GET", "public/v1/notifications/webhooks", query_params=f"eq(object.id,{product_id})"
        ).json()

        purchase_webhook_url = None
        for webhook in webhooks["data"]:
            if webhook["type"] == "ValidatePurchaseOrderDraft":
                purchase_webhook_url = webhook["url"]
            if webhook["type"] == "ValidateTerminateOrder" and webhook["status"] == "Enabled":
                logger.info(
                    "Termination order draft validation webhook already exists for product "
                    "'%s'; skipping",
                    product_id,
                )
                return

        webhook_payload = {
            "type": "ValidateTerminateOrder",
            "status": "Enabled",
            "url": purchase_webhook_url,
            "description": "Termination order draft validation",
            "secret": json.loads(os.environ["EXT_WEBHOOKS_SECRETS"]).get(product_id),
            "criteria": {"product.id": product_id},
        }
        created = self.mpt_client.http_client.request(
            "POST", "public/v1/notifications/webhooks", json=webhook_payload
        ).json()
        logger.info("Created termination webhook '%s' for product '%s'", created["url"], product_id)
