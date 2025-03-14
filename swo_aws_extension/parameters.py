import copy
import functools

from swo_aws_extension.constants import (
    PARAM_MPA_ACCOUNT_ID,
    PARAM_PHASE,
    FulfillmentParameter,
    OrderParameter,
)
from swo_aws_extension.utils import find_first

PARAM_PHASE_ORDERING = "ordering"
PARAM_PHASE_FULFILLMENT = "fulfillment"
PARAM_CONTACT = "contact"


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


def  get_mpa_account_id(source):
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


def get_crm_ticket_id(order):
    """
    Get the CRM ticket ID from the corresponding fulfillment
    parameter or None if it is not set.

    Args:
        order (dict): The order that contains the parameter.

    Returns:
        str: The CRM ticket ID provided by client or None if it isn't set.
    """
    param = get_fulfillment_parameter(
        order,
        FulfillmentParameter.CRM_TICKET_ID,
    )
    return param.get("value", None)


def set_crm_ticket_id(order, crm_ticket_id):
    """
    Set the CRM ticket ID on the fulfillment parameters.

    Args:
        order (dict): The order that contains the parameter.
        crm_ticket_id (str): The CRM ticket ID.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParameter.CRM_TICKET_ID,
    )
    param["value"] = crm_ticket_id
    return updated_order


def get_termination_parameter(order):
    """
    Get the termination flow from the corresponding fulfillment
    parameter or None if it is not set.

    Args:
        order (dict): The order that contains the parameter.

    Returns:
        str: The termination flow provided by client or None if it isn't set.
    """
    param = get_fulfillment_parameter(
        order,
        OrderParameter.TERMINATION,
    )
    return param.get("value", None)


def get_account_id(order):
    """
    Gets the AWS Account ID from the corresponding ordering parameter or None if it is not set.
    :param order: dict
    :return: str | None
    """
    param = get_ordering_parameter(
        order,
        OrderParameter.ACCOUNT_ID,
    )
    return param.get("value", None)
