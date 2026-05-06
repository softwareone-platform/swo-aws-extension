import json
import os

from mpt_tool.migration import SchemaBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin


class Migration(SchemaBaseMigration, MPTAPIClientMixin):
    """Migration to enable change order draft validation."""

    def run(self):
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        self.log.info(
            "Starting migration 20260507080455_project_creation_phase for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            self.log.info("No product IDs found in MPT_PRODUCTS_IDS; nothing to migrate")

        for product_id in product_ids:
            self._migrate_product(product_id)

        self.log.info("Migration 20260507080455_change_draft_validation completed")

    def _migrate_product(self, product_id: str) -> None:
        self.log.info("Migrating product '%s'", product_id)

        self._enable_change_order_validation(product_id)

        self._create_change_order_webhook_if_not_exists(product_id)

    def _enable_change_order_validation(self, product_id):
        product = self.mpt_client.catalog.products.get(product_id).to_dict()
        self.log.info("product '%s'", product["name"])
        if product.get("settings", {}).get("preValidation", {}).get("changeOrderDraft"):
            self.log.info(
                "Change order draft validation already enabled for product '%s'; skipping",
                product_id,
            )
        else:
            product["settings"]["preValidation"]["changeOrderDraft"] = True
            self.log.info(product["settings"])
            self.mpt_client.catalog.products.update_settings(product_id, product["settings"])
            self.log.info("Enabled change order draft validation for product '%s'", product_id)

    def _create_change_order_webhook_if_not_exists(self, product_id):
        webhooks = self.mpt_client.http_client.request(
            "GET", "public/v1/notifications/webhooks", query_params=f"eq(object.id,{product_id})"
        ).json()

        webhook_created = False
        purchase_webhook_url = None
        for webhook in webhooks["data"]:
            if webhook["type"] == "ValidatePurchaseOrderDraft":
                purchase_webhook_url = webhook["url"]
            if webhook["type"] == "ValidateChangeOrderDraft" and webhook["status"] == "Enabled":
                webhook_created = True
        if webhook_created:
            self.log.info(
                "Change order draft validation webhook already exists for product '%s'; skipping",
                product_id,
            )
        else:
            webhook_payload = {
                "type": "ValidateChangeOrderDraft",
                "status": "Enabled",
                "url": purchase_webhook_url,
                "description": "Change order draft validation",
                "secret": json.loads(os.environ["EXT_WEBHOOKS_SECRETS"]).get(product_id),
                "criteria": {"product.id": product_id},
            }
            webhooks = self.mpt_client.http_client.request(
                "POST", "public/v1/notifications/webhooks", json=webhook_payload
            ).json()
            self.log.info("Created webhook '%s' for product '%s'", webhooks["url"], product_id)
