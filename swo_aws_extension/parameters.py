import copy
import functools
from copy import deepcopy
from enum import StrEnum

from swo_aws_extension.constants import (
    PARAM_MPA_ACCOUNT_ID,
    PARAM_PHASE,
)
from swo_aws_extension.utils import find_first


class OrderingParameters(StrEnum):
    PARAM_ACCOUNT_EMAIL="accountEmail"
    MPA_ACCOUNT_ID = "mpaAccountId"
    TERMINATION_TYPE = "terminationType"


class ParameterPhase(StrEnum):
    ORDERING = "ordering"
    FULFILLMENT = "fulfillment"

PARAM_PHASE_ORDERING = "ordering"
PARAM_PHASE_FULFILLMENT = "fulfillment"
PARAM_CONTACT = "contact"

class Parameter:
    def __init__(
            self,
            order,
            phase,
            external_id
    ):
        self._order = order
        self.phase = phase
        self.external_id = external_id

    @property
    def parameter(self):
        return find_first(
            lambda x: x.get("externalId") == self.external_id,
            self._order["parameters"][self.phase],
            default={},
        )

    @property
    def id(self):
        return self.parameter.get("id")

    @property
    def externalId(self):
        return self.parameter.get("externalId")

    @property
    def value(self):
        return self.parameter.get("value")

    def _clone(self):
        new_order = deepcopy(self.order)
        return Parameter(
            new_order,
            self.phase,
            self.external_id
        )

    def update_value(self, v) -> "Parameter":
        new_param = self._clone()
        new_param.parameter["value"] = v
        assert new_param.parameter["value"] == v

        return new_param


    @property
    def error(self):
        return self.parameter.get("error")


    def update_error(self, e) -> "Parameter":
        new_param = self._clone()
        new_param.parameter["error"] = e
        assert new_param.parameter["error"] == e
        return self

    @property
    def constraints(self):
        return self.parameter.get("constraints")

    @property
    def name(self):
        return self.parameter.get("name")

    @property
    def order(self):
        return self._order




class ParameterBag:

    def __init__(self, order, phase):
        self.order = order
        self.phase = phase

    def get_by_external_id(self, external_id: str) -> Parameter:
        param = find_first(
            lambda x: x.get("externalId") == external_id,
            self.order["parameters"][self.phase],
            default=None,
        )
        if not param:
            raise ValueError(f"Parameter {external_id=} not found")
        return Parameter(self.order, self.phase, external_id)

    def get_by_id(self, id: str) -> Parameter:
        param = find_first(
            lambda x: x.get("id") == id,
            self.parameters,
            default=None,
        )
        if not param:
            raise ValueError(f"Parameter {id=} not found")
        return Parameter(param)

    def raw(self):
        return self.parameters

    def update(self):
        self.parameters=[p.raw() for p in self.parameters]
        self.parent.update()


class Parameters:
    def __init__(self, order):
        self.order = order

    @property
    def ordering(self):
        return ParameterBag(
            self.order,
            ParameterPhase.ORDERING
        )

    @property
    def fulfillment(self):
        return ParameterBag(
            self.order,
            ParameterPhase.FULFILLMENT
        )

    def raw(self):
        return {
            ParameterPhase.ORDERING: self.ordering.raw(),
            ParameterPhase.FULFILLMENT: self.fulfillment.raw(),
        }

    def update(self):
        self.context.order["parameters"] = self.parameters.raw()
        return self.context



def get_parameter(parameter_phase, source, param_external_id):
    """
    Returns a parameter of a given phase by its external identifier.
    Returns an empty dictionary if the parameter is not found.
    Args:
        parameter_phase (str): The phase of the parameter (ordering, fulfillment).
        source (str): The source business object from which the parameter
        should be extracted.
        param_external_id (str): The unique external identifier of the parameter.

    Returns:
        dict: The parameter object or an empty dictionary if not found.
    """
    return find_first(
        lambda x: x.get("externalId") == param_external_id,
        source["parameters"][parameter_phase],
        default={},
    )


get_ordering_parameter = functools.partial(get_parameter, PARAM_PHASE_ORDERING)

get_fulfillment_parameter = functools.partial(get_parameter, PARAM_PHASE_FULFILLMENT)


def set_ordering_parameter_error(order, param_external_id, error, required=True):
    """
    Set a validation error on an ordering parameter.

    Args:
        order (dict): The order that contains the parameter.
        param_external_id (str): The external identifier of the parameter.
        error (dict): The error (id, message) that must be set.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_ordering_parameter(
        updated_order,
        param_external_id,
    )
    param["error"] = error
    param["constraints"] = {
        "hidden": False,
        "required": required,
    }
    return updated_order


def get_mpa_account_id(source):
    """
    Get the MPA Account ID from the corresponding fulfillment
    parameter or None if it is not set.

    Args:
        source (dict): The business object from which the MPA Account ID
        should be retrieved.

    Returns:
        str: The MPA Account ID provided by client or None if it isn't set.
    """
    param = get_fulfillment_parameter(
        source,
        PARAM_MPA_ACCOUNT_ID,
    )
    return param.get("value", None)


def get_phase(source):
    """
    Get the phase from the corresponding fulfillment parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the MPA Account ID
        should be retrieved.

    Returns:
        str: The phase of the order.
    """
    param = get_fulfillment_parameter(
        source,
        PARAM_PHASE,
    )
    return param.get("value", None)


def set_phase(order, phase):
    """
    Set the phase on the fulfillment parameters.

    Args:
        order (dict): The order that contains the parameter.
        phase (str): The phase of the order.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_fulfillment_parameter(
        updated_order,
        PARAM_PHASE,
    )
    param["value"] = phase
    return updated_order
