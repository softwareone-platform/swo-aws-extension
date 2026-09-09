# FinOps (FFC Operations)

Manages billing entitlements that map AWS datasources to external affiliates. The extension creates an entitlement when a new customer subscription is activated, and terminates or deletes it when the subscription ends.

The entitlements API is served by the FinOps extension operations endpoint (`/ops/v1`), not by the legacy FFC operations API.

## Authentication

Bearer token. The `FinOpsClient` reuses the Marketplace API token already configured for the extension (`MPT_API_TOKEN`) and sends it on every request:

```http
Authorization: Bearer <MPT_API_TOKEN>
Accept: application/json
Content-Type: application/json
X-Request-Id: <uuid4, unique per request>
```

No token generation or refresh happens in the client. Rotating `MPT_API_TOKEN` rotates the FinOps credentials as well, but the `FinOpsClient` singleton reads the token only when it is created and does not refresh its session headers. Restart the api and worker workloads after rotating the token so the new value is picked up.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_FFC_OPERATIONS_API_BASE_URL` | FinOps extension operations API base URL, including the `/ops/v1` path (for example `https://ext-xxxx-xxxx.ext.s1.show/ops/v1`) |
| `MPT_API_TOKEN` | Marketplace API token, shared with the MPT client and used as the bearer token for FinOps calls |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Create Entitlement | `POST` | `/entitlements` | Creates an entitlement for a datasource/affiliate pair |
| Get Entitlement | `GET` | `/entitlements/{id}` | Returns the entitlement by its identifier (for example `FENT-2289-7693-2555`) |
| Get Entitlement by Datasource | `GET` | `/entitlements?datasource_id={id}&limit=1` | Returns the entitlement linked to a datasource, or `null` |
| Terminate Entitlement | `POST` | `/entitlements/{id}/terminate` | Marks the entitlement as terminated |
| Delete Entitlement | `DELETE` | `/entitlements/{id}` | Permanently removes the entitlement (`204 No Content`) |

### Create Entitlement Payload

```json
{
  "name": "AWS",
  "affiliate_external_id": "<affiliate_id>",
  "datasource_id": "<datasource_id>"
}
```

## Code Reference

Client: [`swo_aws_extension/swo/finops/client.py`](../../swo_aws_extension/swo/finops/client.py)
