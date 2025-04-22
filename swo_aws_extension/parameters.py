import copy
import functools
from enum import StrEnum

from mpt_extension_sdk.mpt_http.utils import find_first

PARAM_PHASE_ORDERING = "ordering"
PARAM_PHASE_FULFILLMENT = "fulfillment"

MAX_ACCOUNT_TRANSFER = 20


class OrderParametersEnum(StrEnum):
    ACCOUNT_TYPE = "accountType"
    ROOT_ACCOUNT_EMAIL = "orderRootAccountEmail"
    ACCOUNT_NAME = "orderAccountName"
    TERMINATION = "terminationType"
    ACCOUNT_ID = "orderAccountId"
    SUPPORT_TYPE = "supportType"
    TRANSFER_TYPE = "transferType"
    PARAM_CONTACT = "contact"
    MASTER_PAYER_ID = "masterPayerId"


class FulfillmentParametersEnum(StrEnum):
    PHASE = "phase"
    ACCOUNT_REQUEST_ID = "accountRequestId"
    ACCOUNT_EMAIL = "accountEmail"
    ACCOUNT_NAME = "accountName"
    CRM_TICKET_ID = "crmTicketId"
    EXISTING_ACCOUNT_CRM_TICKET = "existingAccountCRMTicket"
    CCP_ENGAGEMENT_ID = "ccpEngagementId"


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


def update_ordering_parameter_constraints(order, param_external_id, hidden, required, readonly):
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
        FulfillmentParametersEnum.PHASE,
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
        FulfillmentParametersEnum.PHASE,
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
        OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
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
        OrderParametersEnum.ACCOUNT_NAME,
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
        FulfillmentParametersEnum.ACCOUNT_REQUEST_ID,
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
        FulfillmentParametersEnum.ACCOUNT_REQUEST_ID,
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
        OrderParametersEnum.ACCOUNT_TYPE,
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


def get_master_payer_id(source):
    """
    Get the master payer ID from the corresponding ordering
    parameter or None if it is not set.

    Args:
        source (dict): The business object from which the master payer ID
        should be retrieved.

    Returns:
        str: The master payer ID provided by client or None if it isn't set.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.MASTER_PAYER_ID,
    )
    return param.get("value", None)


def get_link_account_service_ticket_id(source):
    """
    Get the link account service ticket ID from the corresponding fulfillment
    parameter or None if it is not set.

    Args:
        source (dict): The business object from which the link account service ticket ID
        should be retrieved.

    Returns:
        str: The link account service ticket ID provided by client or None if it isn't set.
    """
    param = get_fulfillment_parameter(
        source,
        FulfillmentParametersEnum.EXISTING_ACCOUNT_CRM_TICKET,
    )
    return param.get("value", None)


def set_link_account_service_ticket_id(order, crm_ticket_id):
    """
    Set the link account service ticket ID from the corresponding fulfillment
    parameter or None if it is not set.

    Args:
        order (dict): The business object from which the link account service ticket ID
        should be retrieved.
        crm_ticket_id (str): The link account service ticket ID provided by client.

    Returns:
        str: The link account service ticket ID provided by client or None if it isn't set.
    """
    updated_order = copy.deepcopy(order)
    param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.EXISTING_ACCOUNT_CRM_TICKET,
    )
    param["value"] = crm_ticket_id
    return updated_order


def get_ccp_engagement_id(source):
    """
    Get the CCP engagement ID from the corresponding fulfillment
    parameter or None if it is not set.
    Args:
        source (dict): The order that contains the parameter.
    Returns:
        str: The CCP engagement ID provided by client or None if it isn't set.
    """
    param = get_fulfillment_parameter(
        source,
        FulfillmentParametersEnum.CCP_ENGAGEMENT_ID,
    )
    return param.get("value", None)


def set_ccp_engagement_id(source, ccp_customer_url):
    """
    Set the CCP engagement ID on the fulfillment parameters.
    Args:
        source (dict): The order that contains the parameter.
        ccp_customer_url (str): The CCP engagement ID provided by client.
    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(source)
    param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.CCP_ENGAGEMENT_ID,
    )
    param["value"] = ccp_customer_url
    return updated_order


def get_account_id(source):
    """
    Get the account ID from the corresponding ordering parameter or an empty
     string if it is not set.

    Args:
        source (dict): The business object from which the account ID
        should be retrieved.

    Returns:
        str: The account ID of the order.
    """
    param = get_ordering_parameter(
        source,
        OrderParametersEnum.ACCOUNT_ID,
    )
    return param.get("value", None)
