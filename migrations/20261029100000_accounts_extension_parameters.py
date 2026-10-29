import logging
import os
from collections.abc import Mapping
from typing import Any

from mpt_api_client.rql.query_builder import RQLQuery
from mpt_tool.migration import SchemaBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

logger = logging.getLogger(__name__)

_BILLING_TRANSFER_ACCEPTANCE_DATE_EXTERNAL_ID = "billingTransferAcceptanceDate"
_HANDSHAKE_EXPIRATION_DATE_EXTERNAL_ID = "handshakeExpirationDate"
_MANAGEMENT_ACCOUNT_NAME_EXTERNAL_ID = "managementAccountName"

_billing_transfer_acceptance_date_parameter = {
    "name": "Billing Transfer Acceptance Date",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Date when the customer accepted the AWS billing transfer to SoftwareOne",
    "multiple": False,
    "externalId": _BILLING_TRANSFER_ACCEPTANCE_DATE_EXTERNAL_ID,
    "displayOrder": 160,
    "constraints": {"hidden": False, "readonly": True, "required": False},
    "options": {
        "dateRange": False,
        "placeholderText": "Billing Transfer Acceptance Date",
        "hintText": "Billing Transfer Acceptance Date",
        "type": "Date",
    },
    "type": "Date",
    "status": "Active",
}

_handshake_expiration_date_parameter = {
    "name": "Handshake Expiration Date",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Last day of the fixed commitment period agreed in the channel handshake",
    "multiple": False,
    "externalId": _HANDSHAKE_EXPIRATION_DATE_EXTERNAL_ID,
    "displayOrder": 170,
    "constraints": {"hidden": False, "readonly": True, "required": False},
    "options": {
        "dateRange": False,
        "placeholderText": "Handshake Expiration Date",
        "hintText": "Handshake Expiration Date",
        "type": "Date",
    },
    "type": "Date",
    "status": "Active",
}

_management_account_name_parameter = {
    "name": "Management Account Name",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Name of the AWS management account",
    "multiple": False,
    "externalId": _MANAGEMENT_ACCOUNT_NAME_EXTERNAL_ID,
    "displayOrder": 180,
    "constraints": {"hidden": False, "readonly": True, "required": False},
    "options": {
        "placeholderText": "Management Account Name",
        "hintText": "Management Account Name",
    },
    "type": "SingleLineText",
    "status": "Active",
}

_new_parameters = (
    _billing_transfer_acceptance_date_parameter,
    _handshake_expiration_date_parameter,
    _management_account_name_parameter,
)


def _empty_value(parameter_data: Mapping[str, Any]) -> str | None:
    # MPT rejects an empty string for a Date parameter, so a date starts as null.
    return None if parameter_data["type"] == "Date" else ""


class Migration(SchemaBaseMigration, MPTAPIClientMixin):
    """Migration to add the AWS Accounts extension agreement fulfillment parameters."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        logger.info(
            "Starting migration 20261029100000_accounts_extension_parameters for %s product(s)",
            len(product_ids),
        )

        if not product_ids:
            # Failing keeps the migration pending, so it runs once the products are configured.
            raise ValueError("MPT_PRODUCTS_IDS must contain at least one product ID")

        for product_id in product_ids:
            self._migrate_product(product_id)

        logger.info("Migration 20261029100000_accounts_extension_parameters finished")

    def _migrate_product(self, product_id: str) -> None:
        logger.info("Migrating product '%s'", product_id)

        for parameter_data in _new_parameters:
            existing = self._get_product_parameter(product_id, parameter_data["externalId"])
            self._ensure_parameter(product_id, existing, parameter_data)
        self._migrate_agreements(product_id)

    def _migrate_agreements(self, product_id: str) -> None:
        logger.info("Migrating agreements for product '%s'", product_id)
        query = RQLQuery(product__id=product_id) & RQLQuery(status="Active")
        # Agreements are streamed page by page while being updated, so a stable order keeps
        # the offset pagination from skipping or repeating agreements.
        agreements = (
            self.mpt_client.commerce.agreements
            .filter(query)
            .select("+parameters")
            .order_by("id")
            .iterate()
        )
        checked_count = 0
        updated_count = 0
        for agreement in agreements:
            checked_count += 1
            if self._ensure_agreement_parameters(agreement.to_dict()):
                updated_count += 1
        logger.info(
            "Checked %s active agreement(s) for product '%s'; updated %s",
            checked_count,
            product_id,
            updated_count,
        )

    def _ensure_agreement_parameters(self, agreement: dict[str, Any]) -> bool:
        agreement_id = agreement["id"]
        fulfillment_params = agreement.get("parameters", {}).get("fulfillment", [])
        present_external_ids = {parameter.get("externalId") for parameter in fulfillment_params}
        missing_parameters = [
            parameter_data
            for parameter_data in _new_parameters
            if parameter_data["externalId"] not in present_external_ids
        ]
        if not missing_parameters:
            logger.info(
                "All new parameters already exist for agreement '%s'; skipping", agreement_id
            )
            return False
        logger.info(
            "Adding parameters %s to agreement '%s'",
            ", ".join(parameter_data["externalId"] for parameter_data in missing_parameters),
            agreement_id,
        )
        self.mpt_client.commerce.agreements.update(
            agreement_id,
            {
                "parameters": {
                    "fulfillment": [
                        {
                            "externalId": parameter_data["externalId"],
                            "value": _empty_value(parameter_data),
                        }
                        for parameter_data in missing_parameters
                    ]
                }
            },
        )
        return True

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
