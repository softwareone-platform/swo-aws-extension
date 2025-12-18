import functools

from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.constants import FulfillmentParameters


def get_parameter(parameter_phase, param_external_id, source):
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
        lambda elem: elem.get("externalId") == param_external_id,
        source["parameters"][parameter_phase],
        default={},
    )


get_fulfillment_parameter = functools.partial(get_parameter, FulfillmentParameters.PHASE)
get_responsibility_transfer_id = functools.partial(
    get_fulfillment_parameter, FulfillmentParameters.RESPONSIBILITY_TRANSFER_ID
)
