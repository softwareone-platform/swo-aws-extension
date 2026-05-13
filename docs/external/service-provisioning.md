# Services Provisioning API

Provisions customer service allocations in SoftwareOne's internal service management platform based on CCO contract enrollments. The extension calls this API after a CCO contract is created to onboard the customer's service contacts and return an ERP project number.

## Authentication

OAuth 2.0 Client Credentials. The `OAuthSessionClient` base class refreshes the bearer token transparently before each request. Every request also carries an `x-api-version: 1.0` header.

```http
POST <EXT_SVC_PROVISIONING_OAUTH_URL>
Content-Type: application/x-www-form-urlencoded

client_id=<EXT_SVC_PROVISIONING_CLIENT_ID>
client_secret=<EXT_SVC_PROVISIONING_CLIENT_SECRET>
grant_type=client_credentials
audience=<EXT_SVC_PROVISIONING_AUDIENCE>
```

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_SVC_PROVISIONING_API_BASE_URL` | Base URL for the Service Provisioning API |
| `EXT_SVC_PROVISIONING_OAUTH_URL` | OAuth token endpoint |
| `EXT_SVC_PROVISIONING_CLIENT_ID` | OAuth client ID |
| `EXT_SVC_PROVISIONING_CLIENT_SECRET` | OAuth client secret |
| `EXT_SVC_PROVISIONING_AUDIENCE` | Token audience parameter |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Onboard Service | `POST` | `service-provisioning/api/serviceonboarding` | Onboards a CCO contract and returns `{"erpProjectNo": "PRJ-9999"}` |

Example onboard payload:

```json
{
  "erpClientId": "SWO_CH_01",
  "contractNo": "CCO-12345",
  "serviceDescription": "AWS Cloud",
  "contacts": [
    {
      "firstName": "John",
      "lastName": "Doe",
      "email": "jdoe@example.com",
      "phoneNumber": "+1234567890",
      "languageCode": "en"
    }
  ]
}
```

All operations send `Authorization: Bearer <token>` and `x-api-version: 1.0`.

## Code Reference

Client: [`swo_aws_extension/swo/service_provisioning/client.py`](../../swo_aws_extension/swo/service_provisioning/client.py)
Models: [`swo_aws_extension/swo/service_provisioning/models.py`](../../swo_aws_extension/swo/service_provisioning/models.py)
