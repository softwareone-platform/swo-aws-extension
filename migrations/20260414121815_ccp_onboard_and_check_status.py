import os

from mpt_api_client.rql.query_builder import RQLQuery
from mpt_tool.migration import DataBaseMigration
from mpt_tool.migration.mixins import MPTAPIClientMixin

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
            {"label": "Create Subscriptions", "value": "createSubscription"},
            {"label": "Completed", "value": "completed"},
        ],
        "hintText": "Fulfillment phase",
    }
}

_execution_arn_parameter = {
    "name": "Execution ARN",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Execution ARN",
    "multiple": False,
    "externalId": "executionArn",
    "displayOrder": 100,
    "constraints": {"hidden": False, "readonly": False, "required": False},
    "options": {"placeholderText": "Execution ARN", "hintText": "Execution ARN"},
    "type": "SingleLineText",
    "status": "Active",
}

_deploy_error_notified_parameter = {
    "name": "Feature Version Deployment Error Notified",
    "scope": "Agreement",
    "phase": "Fulfillment",
    "context": "None",
    "description": "Feature Version Deployment Error Notified",
    "multiple": False,
    "externalId": "featureVersionDeploymentErrorNotified",
    "displayOrder": 100,
    "constraints": {"hidden": False, "readonly": False, "required": False},
    "options": {
        "placeholderText": "Feature Version Deployment Error Notified",
        "description": "Feature Version Deployment Error Notified",
        "optionsList": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}],
        "defaultValue": "no",
        "hintText": "Feature Version Deployment Error Notified",
    },
    "type": "DropDown",
    "status": "Active",
}


class Migration(DataBaseMigration, MPTAPIClientMixin):
    """Migration for onboard services and check onboard status product parameters."""

    def run(self) -> None:
        """Run the migration."""
        raw_ids = os.environ["MPT_PRODUCTS_IDS"].replace(" ", "").split(",")
        product_ids = list(filter(None, raw_ids))
        for product_id in product_ids:
            execution_arn_product_parameter = self._get_product_parameter(
                product_id, "executionArn"
            )
            deploy_error_notified_parameter = self._get_product_parameter(
                product_id, "featureVersionDeploymentErrorNotified"
            )
            self._update_product_phases(product_id)
            if not execution_arn_product_parameter:
                self._create_product_parameter(product_id, _execution_arn_parameter)
            if not deploy_error_notified_parameter:
                self._create_product_parameter(product_id, _deploy_error_notified_parameter)

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
            product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
            product_parameters_service.update(phase_parameter.id, _phases_options)

    def _create_product_parameter(self, product_id: str, parameter_data: dict):
        product_parameters_service = self.mpt_client.catalog.products.parameters(product_id)
        product_parameters_service.create(parameter_data)
