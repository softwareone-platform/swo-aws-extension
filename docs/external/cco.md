# CCO API (Contract Creation Online)

Registers and retrieves commercial contracts within Navision (SoftwareOne's internal ERP). The extension creates a CCO contract when a new AWS customer subscription is confirmed, and queries existing contracts when processing Master Payer Account (MPA) related orders.

## Authentication

OAuth 2.0 Client Credentials. The `OAuthSessionClient` base class refreshes the bearer token transparently before each request.

```http
POST <EXT_CCO_OAUTH_URL>
Content-Type: application/x-www-form-urlencoded

client_id=<EXT_CCO_CLIENT_ID>
client_secret=<EXT_CCO_CLIENT_SECRET>
grant_type=client_credentials
audience=<EXT_CCO_AUDIENCE>
```

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_CCO_API_BASE_URL` | Base URL for the CCO API |
| `EXT_CCO_OAUTH_URL` | OAuth token endpoint |
| `EXT_CCO_CLIENT_ID` | OAuth client ID |
| `EXT_CCO_CLIENT_SECRET` | OAuth client secret |
| `EXT_CCO_AUDIENCE` | Token audience parameter |
| `EXT_CCO_MANUFACTURER_CODE` | Manufacturer code injected into every contract creation request |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Create CCO Contract | `POST` | `v1/contracts` | Creates a new contract; returns `{"contractInsert": {"contractNumber": "CCO-12345"}}` |
| Get All MPA Contracts | `GET` | `v1/contracts/all/{mpa_id}` | Returns all contracts for a Master Payer Account |
| Get Contract by ID | `GET` | `v1/contracts/{cco_id}` | Returns a single contract, or `null` if not found (`404`) |

Example create payload:

```json
{
  "softwareOneLegalEntity": "SWO_CH_01",
  "contractNumberReference": "123456789012",
  "customerNumber": "CUST-123",
  "customerReference": "CUST-REF-999",
  "enrollmentNumber": "ENR-456",
  "manufacturerCode": "SWOTS",
  "startDate": "2024-01-01T00:00:00",
  "currencyCode": "USD",
  "licenseModel": "CAW-0046",
  "contractCategory": "CLOUD-BASI"
}
```

## Code Reference

Client: [`swo_aws_extension/swo/cco/client.py`](../../swo_aws_extension/swo/cco/client.py)
Models: [`swo_aws_extension/swo/cco/models.py`](../../swo_aws_extension/swo/cco/models.py)
