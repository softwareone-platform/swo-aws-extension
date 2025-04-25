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
    CONTACT = "contact"
    MASTER_PAYER_ID = "masterPayerId"


class FulfillmentParametersEnum(StrEnum):
    PHASE = "phase"
    ACCOUNT_REQUEST_ID = "accountRequestId"
    ACCOUNT_EMAIL = "accountEmail"
    ACCOUNT_NAME = "accountName"
    CRM_ONBOARD_TICKET_ID = "crmOnboardTicketId"
    CRM_KEEPER_TICKET_ID = "crmKeeperTicketId"
    CRM_TERMINATION_TICKET_ID = "crmTerminationTicketId"
    CRM_CCP_TICKET_ID = "crmCCPTicketId"
    CRM_TRANSFER_ORGANIZATION_TICKET_ID = "crmTransferOrganizationTicketId"
    CCP_ENGAGEMENT_ID = "ccpEngagementId"
    MPA_EMAIL = "mpaEmail"


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


def set_support_type(order, support_type):
    """
    Set the support type on the ordering parameters.

    Args:
        order (dict): The order that contains the parameter.
        support_type (str): The support type of the order.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_ordering_parameter(
        updated_order,
        OrderParametersEnum.SUPPORT_TYPE,
    )
    param["value"] = support_type
    return updated_order


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


def get_crm_keeper_ticket_id(order):
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
        FulfillmentParametersEnum.CRM_KEEPER_TICKET_ID,
    )
    return param.get("value", None)


def set_crm_keeper_ticket_id(order, crm_ticket_id):
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
        FulfillmentParametersEnum.CRM_KEEPER_TICKET_ID,
    )
    param["value"] = crm_ticket_id
    return updated_order


def get_crm_termination_ticket_id(order):
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
        FulfillmentParametersEnum.CRM_TERMINATION_TICKET_ID,
    )
    return param.get("value", None)


def set_crm_termination_ticket_id(order, crm_ticket_id):
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
        FulfillmentParametersEnum.CRM_TERMINATION_TICKET_ID,
    )
    param["value"] = crm_ticket_id
    return updated_order


def get_crm_ccp_ticket_id(order):
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
        FulfillmentParametersEnum.CRM_CCP_TICKET_ID,
    )
    return param.get("value", None)


def set_crm_ccp_ticket_id(order, crm_ticket_id):
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
        FulfillmentParametersEnum.CRM_CCP_TICKET_ID,
    )
    param["value"] = crm_ticket_id
    return updated_order


def get_crm_onboard_ticket_id(source):
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
        FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID,
    )
    return param.get("value", None)


def set_crm_onboard_ticket_id(order, crm_ticket_id):
    """
    Set the Onboard service ticket ID from the corresponding fulfillment
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
        FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID,
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


def set_parameter_value(order, parameter_id, value):
    """
    Set the value of a parameter in the order.
    Args:
        order (dict): The order that contains the parameter.
        parameter_id (str): The external identifier of the parameter.
        value (any): The value to set for the parameter.
    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_ordering_parameter(
        updated_order,
        parameter_id,
    )
    param["value"] = value
    return updated_order


def reset_ordering_parameters(order, list_parameters):
    """
    Reset the ordering parameters to empty string and update their constraints
    to be hidden, not required, and not readonly.
    Args:
        order: The order object to update.
        list_parameters: List of parameter IDs to reset.

    Returns:
        The updated order object.
    """
    updated_order = copy.deepcopy(order)
    for parameter_id in list_parameters:
        updated_order = set_parameter_value(updated_order, parameter_id, None)
        updated_order = update_ordering_parameter_constraints(
            updated_order,
            parameter_id,
            hidden=True,
            required=False,
            readonly=False,
        )

    return updated_order


def list_ordering_parameters_with_errors(order) -> list[str]:
    """
    List all ordering parameters externalId with errors.
    Args:
        order (dict): The order that contains the parameter.

    Returns:
        list: List of parameter external IDs with errors.
    """
    return [
        param.get("externalId")
        for param in order["parameters"][PARAM_PHASE_ORDERING]
        if param.get("error")
    ]


def set_ordering_parameters_to_readonly(order, ignore: list[str], hide_param=True):
    """
    Set the readonly constraint on all ordering parameters except the ones in ignore list
    Args:
        order (dict): The order that contains the parameter.
        ignore (list): List of parameter external IDs to not set as readonly.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)

    for param in updated_order["parameters"][PARAM_PHASE_ORDERING]:
        if param.get("externalId") in ignore:
            continue
        if "constraints" not in param or not param["constraints"]:
            param["constraints"] = {}
        param["constraints"]["readonly"] = True
        if hide_param:
            param["constraints"]["hidden"] = True

    return updated_order


def get_mpa_email(order):
    """
    Get the MPA email from the corresponding fulfillment parameter or None if it is not set.

    Args:
        order (dict): The order that contains the parameter.

    Returns:
        str: The MPA email provided by client or None if it isn't set.
    """
    param = get_fulfillment_parameter(
        order,
        FulfillmentParametersEnum.MPA_EMAIL,
    )
    return param.get("value", None)


def set_mpa_email(order, mpa_email):
    """
    Set the MPA email on the fulfillment parameters.

    Args:
        order (dict): The order that contains the parameter.
        mpa_email (str): The MPA email of the order.

    Returns:
        dict: The order updated.
    """
    updated_order = copy.deepcopy(order)
    param = get_fulfillment_parameter(
        updated_order,
        FulfillmentParametersEnum.MPA_EMAIL,
    )
    param["value"] = mpa_email
    return updated_order


def get_crm_transfer_organization_ticket_id(order):
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
        FulfillmentParametersEnum.CRM_TRANSFER_ORGANIZATION_TICKET_ID,
    )
    return param.get("value", None)


def set_crm_transfer_organization_ticket_id(order, crm_ticket_id):
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
        FulfillmentParametersEnum.CRM_TRANSFER_ORGANIZATION_TICKET_ID,
    )
    param["value"] = crm_ticket_id
    return updated_order
