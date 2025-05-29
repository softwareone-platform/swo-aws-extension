import logging
from copy import deepcopy

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.parameters import (
    PARAM_PHASE_ORDERING,
)

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

    def process_parameters(self, parameters):
        """
        Shows parameters with values and hides those without values.
        """

        new_parameters = []
        for p in parameters:
            if not p.get("value"):
                np = self.set_hidden_paramter(p, hidden=True)
                new_parameters.append(np)
                continue
            np = self.set_hidden_paramter(p)
            new_parameters.append(np)
        return new_parameters

    def setup_order_parameters(self, client, context):
        ordering = context.order.get("parameters", {}).get("ordering", [])
        context.order["parameters"][PARAM_PHASE_ORDERING] = self.process_parameters(ordering)

        context.order = update_order(
            client, context.order_id, paramaters=context.order["parameters"]
        )

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        self.setup_order_parameters(client, context)
        logger.info(f"{context.order_id} - Action - Updated parameters visibility")
        next_step(client, context)
