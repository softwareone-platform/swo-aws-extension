import datetime as dt

import jwt
import pytest
import responses
from freezegun import freeze_time

from swo_aws_extension.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_INTERNAL_SERVER_ERROR,
    HTTP_STATUS_NO_CONTENT,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from swo_aws_extension.swo_finops.client import FinOpsHttpError, FinOpsNotFoundError, get_ffc_client


def test_finops_http_error():
    error = FinOpsHttpError(HTTP_STATUS_BAD_REQUEST, "Nothing")

    assert str(error) == "400 - Nothing"


def test_finops_not_found_error():
    error = FinOpsNotFoundError("Nothing")

    assert str(error) == "404 - Nothing"


@freeze_time("2025-01-01")
@responses.activate
def test_create_entitlement(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.post(
        "https://local.local/entitlements",
        status=HTTP_STATUS_OK,
        json={"id": "12345", "name": "AWS"},
        match=[
            responses.matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
            responses.matchers.json_params_matcher({
                "name": "AWS",
                "affiliate_external_id": "aff123",
                "datasource_id": "ds123",
            }),
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
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.post(
        "https://local.local/entitlements",
        status=HTTP_STATUS_OK,
        json={"id": "12345", "name": "AWS"},
        match=[
            responses.matchers.header_matcher(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-Id": "uuid-1",
                },
            ),
            responses.matchers.json_params_matcher({
                "name": "AWS",
                "affiliate_external_id": "aff123",
                "datasource_id": "ds123",
            }),
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
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.delete(
        "https://local.local/entitlements/ent123",
        status=HTTP_STATUS_NO_CONTENT,
        match=[
            responses.matchers.header_matcher(
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

    response = client.delete_entitlement("ent123")

    assert not response


@freeze_time("2025-01-01")
@responses.activate
def test_terminate_entitlement(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.post(
        "https://local.local/entitlements/ent123/terminate",
        status=HTTP_STATUS_OK,
        json={"id": "ent123", "status": "terminated"},
        match=[
            responses.matchers.header_matcher(
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
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=HTTP_STATUS_OK,
        json={"items": [{"id": "ent123", "datasource_id": "ds123"}], "total": 1},
        match=[
            responses.matchers.header_matcher(
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
def test_entitlement_by_ds_id_not_found(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=HTTP_STATUS_OK,
        json={"items": [], "total": 0},
        match=[
            responses.matchers.header_matcher(
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
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=HTTP_STATUS_INTERNAL_SERVER_ERROR,
        json={"error": "Internal Server Error"},
        match=[
            responses.matchers.header_matcher(
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

    assert exc_info.value.status_code == HTTP_STATUS_INTERNAL_SERVER_ERROR
    assert exc_info.value.response_content == {"error": "Internal Server Error"}


@freeze_time("2025-01-01")
@responses.activate
def test_not_found_error_handling(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    now = dt.datetime.now(tz=dt.UTC)
    token = mock_jwt_encoder(now)
    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=HTTP_STATUS_NOT_FOUND,
        json={"error": "Not Found"},
        match=[
            responses.matchers.header_matcher(
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

    assert exc_info.value.status_code == HTTP_STATUS_NOT_FOUND
    assert exc_info.value.response_content == {"error": "Not Found"}


@freeze_time("2025-01-01")
@responses.activate
def test_token_expired_handling(mocker, mock_jwt_encoder, ffc_client_settings):
    mocker.patch(
        "swo_aws_extension.swo_finops.client.uuid4",
        return_value="uuid-1",
    )
    initial_token = mock_jwt_encoder(dt.datetime.now(tz=dt.UTC))
    new_token = mock_jwt_encoder(dt.datetime.now(tz=dt.UTC))
    mock_decode = mocker.patch("jwt.decode")
    mock_decode.side_effect = [jwt.ExpiredSignatureError(), None]
    mock_encode = mocker.patch("jwt.encode")
    mock_encode.return_value = new_token
    responses.get(
        "https://local.local/entitlements?datasource_id=ds123&limit=1",
        status=HTTP_STATUS_OK,
        json={"items": [{"id": "ent123", "datasource_id": "ds123"}], "total": 1},
        match=[
            responses.matchers.header_matcher(
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
    client._jwt = initial_token  # noqa: SLF001

    response = client.get_entitlement_by_datasource_id("ds123")

    assert response == {"id": "ent123", "datasource_id": "ds123"}
    assert mock_decode.call_count == 1
    mock_encode.assert_called_once_with(
        {
            "sub": ffc_client_settings.EXTENSION_CONFIG["FFC_SUB"],
            "exp": dt.datetime.now(tz=dt.UTC) + dt.timedelta(minutes=5),
            "nbf": dt.datetime.now(tz=dt.UTC),
            "iat": dt.datetime.now(tz=dt.UTC),
        },
        ffc_client_settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"],
        algorithm="HS256",
    )
