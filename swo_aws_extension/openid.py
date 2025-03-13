import requests


def get_openid_token(endpoint, client_id, client_secret, scope, audience=None):
    """
    Get an access token from an OpenID Connect provider
    :param endpoint: URL of the auth provider
    :param client_id:
    :param client_secret:
    :param scope:
    :param extra:
    :return: response data
    """
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": scope,
        "audience": audience,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(endpoint, headers=headers, data=payload)
    response.raise_for_status()  # Raise an error for bad status codes
    response_data = response.json()
    return response_data
