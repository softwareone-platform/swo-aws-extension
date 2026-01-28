import requests


def get_auth_token(endpoint, client_id, client_secret, scope, audience=None):
    """Get an auth token from the specified endpoint."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": scope,
        "audience": audience,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(endpoint, headers=headers, data=payload, timeout=60)
    response.raise_for_status()
    return response.json()
