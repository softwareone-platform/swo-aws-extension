import logging
from copy import deepcopy

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.flows.order import InitialAWSContext

logger = logging.getLogger(__name__)


class SetParametersVisibleStep(Step):
    def set_hidden_paramter(self, parameter, hidden=False):
        """
        Update the visibility of the parameter to read-only.

        Args:
            parameter (dict): The parameter to update.
        """
        new_parameter = deepcopy(parameter)
        if "constraints" not in new_parameter:
            new_parameter["constraints"] = {}
        new_parameter["constraints"]["hidden"] = hidden
        return new_parameter

    def process_parameters(self, parameters, always_shown=None, always_hidden=None):
        """
        Shows parameters with values and hides those without values.
        """
        if not always_shown:
            always_shown = []
        if not always_hidden:
            always_hidden = []
        new_parameters = []
        for p in parameters:
            if p.get("externalId") in always_shown:
                np = self.set_hidden_paramter(p, hidden=False)
                new_parameters.append(np)
                continue
            if p.get("externalId") in always_hidden:
                np = self.set_hidden_paramter(p, hidden=True)
                new_parameters.append(np)
                continue

            if not p.get("value"):
                np = self.set_hidden_paramter(p, hidden=True)
                new_parameters.append(np)
                continue
            np = self.set_hidden_paramter(p)
            new_parameters.append(np)
        return new_parameters

    def update_all_parameters_visibility(self, client, context):
        ordering = context.order.get("parameters", {}).get("ordering", [])
        context.order["parameters"]["ordering"] = self.process_parameters(ordering)

        fulfillment = context.order.get("fulfillment", {}).get("fulfillment", [])
        context.order["parameters"]["fulfillment"] = self.process_parameters(fulfillment)
        context.order = update_order(
            client, context.order_id, paramaters=context.order["parameters"]
        )

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        self.update_all_parameters_visibility(client, context)
        logger.info(f"{context.order_id} - Action - Updated parameters visibility")
        next_step(client, context)
