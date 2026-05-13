# Service-Now (CRM)

Automates the creation and lifecycle management of Customer Service Requests linked to AWS orders. The extension creates a ticket when an order enters a specific phase, adds comments as the order progresses, and reads the ticket status to decide the next step.

## Authentication

OAuth 2.0 Client Credentials. Every request carries a `Bearer` token, an `x-api-version` header, and an `x-correlation-id` header set to the MPT order ID.

```http
POST <EXT_CRM_OAUTH_URL>
Content-Type: application/x-www-form-urlencoded

client_id=<EXT_CRM_CLIENT_ID>
client_secret=<EXT_CRM_CLIENT_SECRET>
grant_type=client_credentials
audience=<EXT_CRM_AUDIENCE>
```

The `OAuthSessionClient` base class in [`swo_aws_extension/swo/base_client.py`](../../swo_aws_extension/swo/base_client.py) refreshes the token transparently. The CRM client additionally injects `x-api-version: 3.0.0` on every request.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_CRM_API_BASE_URL` | Base URL for the Service-Now API |
| `EXT_CRM_OAUTH_URL` | OAuth token endpoint |
| `EXT_CRM_CLIENT_ID` | OAuth client ID |
| `EXT_CRM_CLIENT_SECRET` | OAuth client secret |
| `EXT_CRM_AUDIENCE` | Token audience parameter |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Create Service Request | `POST` | `/ticketing/ServiceRequests` | Creates a new ticket; returns `{"id": "CS0004728"}` |
| Get Service Request | `GET` | `/ticketing/ServiceRequests/{id}` | Returns service request details |
| Add Comment | `POST` | `/ticketing/ServiceRequests/{id}/comments` | Appends a comment with `{"value": "..."}` |

All operations send `Authorization: Bearer <token>`, `x-api-version: 3.0.0`, and `x-correlation-id: <mpt_order_id>`.

## Code Reference

Client: [`swo_aws_extension/swo/crm_service/client.py`](../../swo_aws_extension/swo/crm_service/client.py)
