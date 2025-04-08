from unittest.mock import patch

from requests.models import Response


def test_get_ccp_access_token(ccp_client, config):
    with patch("swo_ccp_client.client.get_openid_token") as mock_get_token:
        mock_get_token.return_value = {"access_token": "test_access_token"}
        token = ccp_client.get_ccp_access_token()
        assert token == "test_access_token"
        mock_get_token.assert_called_once_with(
            endpoint=config.ccp_oauth_url,
            client_id=config.ccp_client_id,
            client_secret=config.ccp_client_secret,
            scope=config.ccp_oauth_scope,
        )


def test_onboard_customer(
    mocker, ccp_client, mock_onboard_customer_response, onboard_customer_factory
):
    mock_response = mocker.Mock(spec=Response)
    mock_response.json.return_value = mock_onboard_customer_response
    mock_response.status_code = 200
    mocker.patch.object(ccp_client, "post", return_value=mock_response)

    response = ccp_client.onboard_customer(onboard_customer_factory())
    assert response == mock_onboard_customer_response
    ccp_client.post.assert_called_once_with(
        url="/services/aws-essentials/customer?api-version=v2",
        json=onboard_customer_factory(),
    )


def test_get_onboard_status(mocker, ccp_client, onboard_customer_status_factory):
    ccp_engagement_id = "73ae391e-69de-472c-8d05-2f7feb173207"
    mock_response = mocker.Mock(spec=Response)
    mock_response.json.return_value = onboard_customer_status_factory()
    mock_response.status_code = 200
    mocker.patch.object(ccp_client, "get", return_value=mock_response)

    response = ccp_client.get_onboard_status(ccp_engagement_id)
    assert response == onboard_customer_status_factory()
    ccp_client.get.assert_called_once_with(
        url="services/aws-essentials/customer/engagement/"
        "73ae391e-69de-472c-8d05-2f7feb173207?api-version=v2"
    )
