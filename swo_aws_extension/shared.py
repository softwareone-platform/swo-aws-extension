from mpt_extension_sdk.core.utils import setup_client

mpt_client = setup_client()


def find_first_match(dict_data, match_key, match_value):
    """Find the first matching key-value pair in a dictionary.

    Args:
        dict_data (dict): The dictionary to search.
        match_key (str): The key to look for.
        match_value (Decimal): The value to match.

    Returns:
        dict or None: The first matching key-value pair as a dictionary,
         or None if no match is found.
    """
    for dict_key, dict_value in dict_data.items():
        if dict_key == match_key and dict_value == match_value:
            return {dict_key: dict_value}
    return None
