import copy
import functools
from enum import StrEnum

from swo_aws_extension.utils import find_first

PARAM_PHASE_ORDERING = "ordering"
PARAM_PHASE_FULFILLMENT = "fulfillment"
PARAM_CONTACT = "contact"


class OrderParametersEnum(StrEnum):
    PARAM_ACCOUNT_TYPE = "accountType"
    PARAM_ORDER_ROOT_ACCOUNT_EMAIL = "orderRootAccountEmail"
    PARAM_ORDER_ACCOUNT_NAME = "orderAccountName"
    PARAM_ORDER_ACCOUNT_ID = "orderAccountId"
    TERMINATION = "terminationType"
    ACCOUNT_ID = "orderAccountId"
    SUPPORT_TYPE = "supportType"
    TRANSFER_TYPE = "transferType"


class FulfillmentParametersEnum(StrEnum):
    PARAM_MPA_ACCOUNT_ID = "mpaAccountId"
    PARAM_PHASE = "phase"
    PARAM_ACCOUNT_REQUEST_ID = "accountRequestId"
    PARAM_ACCOUNT_EMAIL = "accountEmail"
    PARAM_ACCOUNT_NAME = "accountName"
    CRM_TICKET_ID = "crmTicketId"


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


def reset_ordering_parameters_error(order):
    """
    Reset errors for all ordering parameters

    Args:
        order (dict): The order that contains the parameter.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)

    for param in updated_order["parameters"][PARAM_PHASE_ORDERING]:
        param["error"] = None

    return updated_order


def set_ordering_parameter_error(order, param_external_id, error, required=True):
    """
    Set a validation error on an ordering parameter.

    Args:
        order (dict): The order that contains the parameter.
        param_external_id (str): The external identifier of the parameter.
        error (dict): The error (id, message) that must be set.
        required (bool): Whether the parameter is required or not.

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


def update_ordering_parameter_constraints(
    order, param_external_id, hidden, required, readonly
):
    """
    Update constraints on an ordering parameter.
    Args:
        order (dict): The order that contains the parameter.
        param_external_id (str): The external identifier of the parameter.
        hidden (bool): Whether the parameter is hidden or not.
        required (bool): Whether the parameter is required or not.
        readonly (bool): Whether the parameter is readonly or not.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_ordering_parameter(
        updated_order,
        param_external_id,
    )

    param["constraints"] = {
        "hidden": hidden,
        "required": required,
        "readonly": readonly,
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
        FulfillmentParametersEnum.PARAM_MPA_ACCOUNT_ID,
    )
    return param.get("value", None)


def set_mpa_account_id(order, mpa_account_id):
    """
    Set the MPA Account ID on the fulfillment parameters.

    Args:
        order (dict): The order that contains the parameter.
        mpa_account_id (str): The MPA Account ID provided by client.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.PARAM_MPA_ACCOUNT_ID,
    )
    param["value"] = mpa_account_id
    return updated_order


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
        FulfillmentParametersEnum.PARAM_PHASE,
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
        FulfillmentParametersEnum.PARAM_PHASE,
    )
    param["value"] = phase
    return updated_order


def get_account_email(source):
    """
    Get the email from the corresponding ordering parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the email
        should be retrieved.

    Returns:
        str: The email of the order.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.PARAM_ORDER_ROOT_ACCOUNT_EMAIL,
    )
    return param.get("value", None)


def get_account_name(source):
    """
    Get the account name from the corresponding ordering parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the account name
        should be retrieved.

    Returns:
        str: The account name of the order.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.PARAM_ORDER_ACCOUNT_NAME,
    )
    return param.get("value", None)


def get_account_request_id(source):
    """
    Get the account request id from the corresponding fulfillment parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the account request id
        should be retrieved.

    Returns:
        str: The account request id of the order.
    """
    param = get_fulfillment_parameter(
        source,
        FulfillmentParametersEnum.PARAM_ACCOUNT_REQUEST_ID,
    )
    return param.get("value", None)


def set_account_request_id(order, account_request_id):
    """
    Set the account request id on the fulfillment parameters.

    Args:
        order (dict): The order that contains the parameter.
        account_request_id (str): The account request id of the order.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.PARAM_ACCOUNT_REQUEST_ID,
    )
    param["value"] = account_request_id
    return updated_order


def get_account_type(source):
    """
    Get the account type from the corresponding ordering parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the account type
        should be retrieved.

    Returns:
        str: The account type of the order.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.PARAM_ACCOUNT_TYPE,
    )
    return param.get("value", None)


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
        FulfillmentParametersEnum.CRM_TICKET_ID,
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
        FulfillmentParametersEnum.CRM_TICKET_ID,
    )
    param["value"] = crm_ticket_id
    return updated_order


def get_termination_type_parameter(order):
    """
    Get the termination flow from the corresponding fulfillment
    parameter or None if it is not set.

    Args:
        order (dict): The order that contains the parameter.

    Returns:
        str: The termination flow provided by client or None if it isn't set.
    """
    param = get_ordering_parameter(
        order,
        OrderParametersEnum.TERMINATION,
    )
    return param.get("value", None)


def get_support_type(source):
    """
    Get the support type from the corresponding ordering parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the support type
        should be retrieved.

    Returns:
        str: The support type of the order.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.SUPPORT_TYPE,
    )
    return param.get("value", None)


def get_transfer_type(source):
    """
    Get the transfer type from the corresponding ordering parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the transfer type
        should be retrieved.

    Returns:
        str: The transfer type of the order.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.TRANSFER_TYPE,
    )
    return param.get("value", None)
