import pytest
import requests

from swo_aws_extension.openid import get_openid_token


def test_get_openid_token_success(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"access_token": "test_token"}
    mock_response.raise_for_status = mocker.Mock()
    mock_post = mocker.patch("swo_aws_extension.openid.requests.post", return_value=mock_response)

    endpoint = "https://auth.example.com/oauth/token"
    client_id = "client_id"
    client_secret = "client_secret"
    scope = "scope"
    audience = "audience"

    response = get_openid_token(endpoint, client_id, client_secret, scope, audience)

    assert response == {"access_token": "test_token"}
    mock_post.assert_called_once_with(
        endpoint,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": scope,
            "audience": audience,
        },
    )


def test_get_openid_token_failure(mocker):
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Error")
    mock_post = mocker.patch("swo_aws_extension.openid.requests.post", return_value=mock_response)

    endpoint = "https://auth.example.com/oauth/token"
    client_id = "client_id"
    client_secret = "client_secret"
    scope = "scope"
    audience = "audience"

    with pytest.raises(requests.exceptions.HTTPError):
        get_openid_token(endpoint, client_id, client_secret, scope, audience)

    mock_post.assert_called_once_with(
        endpoint,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": scope,
            "audience": audience,
        },
    )
