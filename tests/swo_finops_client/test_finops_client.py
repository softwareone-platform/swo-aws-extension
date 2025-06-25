from datetime import UTC, datetime, timedelta

import jwt
import pytest
import responses
from freezegun import freeze_time
from responses import matchers

from swo_finops_client.client import FinOpsHttpError, FinOpsNotFoundError, get_ffc_client


def test_finops_http_error():
    error = FinOpsHttpError(400, "Nothing")

    assert str(error) == "400 - Nothing"


def test_finops_not_found_error():
    error = FinOpsNotFoundError("Nothing")

    assert str(error) == "404 - Nothing"


@freeze_time("2025-01-01")
@responses.activate
def test_create_entitlement(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.post(
        "https://local.local/entitlements",
        status=200,
        json={"id": "12345", "name": "AWS"},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
            matchers.json_params_matcher(
                {
                    "name": "AWS",
                    "affiliate_external_id": "aff123",
                    "datasource_id": "ds123",
                }
            ),
        ],
    )

    client = get_ffc_client()
    response = client.create_entitlement(
        affiliate_external_id="aff123",
        datasource_id="ds123",
        name="AWS",
    )

    assert response == {"id": "12345", "name": "AWS"}


@freeze_time("2025-01-01")
@responses.activate
def test_create_entitlement_with_default_name(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.post(
        "https://local.local/entitlements",
        status=200,
        json={"id": "12345", "name": "AWS"},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
            matchers.json_params_matcher(
                {
                    "name": "AWS",
                    "affiliate_external_id": "aff123",
                    "datasource_id": "ds123",
                }
            ),
        ],
    )

    client = get_ffc_client()
    response = client.create_entitlement(
        affiliate_external_id="aff123",
        datasource_id="ds123",
    )

    assert response == {"id": "12345", "name": "AWS"}


@freeze_time("2025-01-01")
@responses.activate
def test_delete_entitlement(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.delete(
        "https://local.local/entitlements/ent123",
        status=204,
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    client.delete_entitlement("ent123")


@freeze_time("2025-01-01")
@responses.activate
def test_terminate_entitlement(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.post(
        "https://local.local/entitlements/ent123/terminate",
        status=200,
        json={"id": "ent123", "status": "terminated"},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    response = client.terminate_entitlement("ent123")

    assert response == {"id": "ent123", "status": "terminated"}


@freeze_time("2025-01-01")
@responses.activate
def test_get_entitlement_by_datasource_id(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=200,
        json={"items": [{"id": "ent123", "datasource_id": "ds123"}], "total": 1},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    response = client.get_entitlement_by_datasource_id("ds123")

    assert response == {"id": "ent123", "datasource_id": "ds123"}


@freeze_time("2025-01-01")
@responses.activate
def test_get_entitlement_by_datasource_id_not_found(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=200,
        json={"items": [], "total": 0},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    response = client.get_entitlement_by_datasource_id("ds123")

    assert response is None


@freeze_time("2025-01-01")
@responses.activate
def test_http_error_handling(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=500,
        json={"error": "Internal Server Error"},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    with pytest.raises(FinOpsHttpError) as exc_info:
        client.get_entitlement_by_datasource_id("ds123")

    assert exc_info.value.status_code == 500
    assert exc_info.value.content == {"error": "Internal Server Error"}


@freeze_time("2025-01-01")
@responses.activate
def test_not_found_error_handling(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    token = mock_jwt_encoder(now)

    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=404,
        json={"error": "Not Found"},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    with pytest.raises(FinOpsNotFoundError) as exc_info:
        client.get_entitlement_by_datasource_id("ds123")

    assert exc_info.value.status_code == 404
    assert exc_info.value.content == {"error": "Not Found"}


@freeze_time("2025-01-01")
@responses.activate
def test_token_expired_handling(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_finops_client.client.uuid4",
        return_value="uuid-1",
    )

    now = datetime.now(tz=UTC)
    initial_token = mock_jwt_encoder(now)
    new_token = mock_jwt_encoder(now)

    mock_decode = mocker.patch("jwt.decode")
    mock_decode.side_effect = [jwt.ExpiredSignatureError(), None]

    mock_encode = mocker.patch("jwt.encode")
    mock_encode.return_value = new_token

    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=200,
        json={"items": [{"id": "ent123", "datasource_id": "ds123"}], "total": 1},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": f"Bearer {new_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
        ],
    )

    client = get_ffc_client()
    client._jwt = initial_token
    response = client.get_entitlement_by_datasource_id("ds123")

    assert response == {"id": "ent123", "datasource_id": "ds123"}
    assert mock_decode.call_count == 1
    mock_encode.assert_called_once_with(
        {
            "sub": ffc_client_settings.EXTENSION_CONFIG["FFC_SUB"],
            "exp": now + timedelta(minutes=5),
            "nbf": now,
            "iat": now,
        },
        ffc_client_settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"],
        algorithm="HS256",
    )
