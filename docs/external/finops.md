# FinOps (FFC Operations)

Manages billing entitlements that map AWS datasources to external affiliates. The extension creates an entitlement when a new customer subscription is activated, and terminates or deletes it when the subscription ends.

## Authentication

Self-signed JSON Web Tokens (JWT). No external token authority is involved. The `FinOpsClient` generates and signs a short-lived JWT (5-minute expiry) using the shared secret before each request.

```json
{
  "sub": "<EXT_FFC_SUB>",
  "exp": <now + 5 minutes>,
  "nbf": <now>,
  "iat": <now>
}
```

Token is signed with `HS256` using `EXT_FFC_OPERATIONS_SECRET` and attached via:

```http
Authorization: Bearer <generated_jwt>
```

The client checks token expiry before each request and re-generates when expired.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_FFC_OPERATIONS_API_BASE_URL` | FFC Operations API base URL |
| `EXT_FFC_SUB` | Subject identifier used in the JWT `sub` claim |
| `EXT_FFC_OPERATIONS_SECRET` | Secret used to sign the JWT (HS256) |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Create Entitlement | `POST` | `/entitlements` | Creates an entitlement for a datasource/affiliate pair |
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
