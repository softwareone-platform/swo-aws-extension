# Cloud Orchestrator

Manages AWS customer onboarding and upgrade processes and bootstrap role deployments. The extension uses this API to trigger customer onboarding, upgrade a migrated account that is already onboarded, verify bootstrap role readiness, and poll deployment execution status.

## Authentication

OAuth 2.0 Client Credentials using an OpenID Bearer token. The client fetches a token from the CCP OAuth endpoint using the `EXT_AWS_OPENID_SCOPE` scope, then attaches it to every request.

```http
POST <EXT_CCP_OAUTH_URL>
Content-Type: application/x-www-form-urlencoded

client_id=<EXT_CCP_CLIENT_ID>
client_secret=<CCP_KEY_VAULT_SECRET>
grant_type=client_credentials
scope=<EXT_AWS_OPENID_SCOPE>
```

The `client_secret` is not stored in environment variables — it is retrieved at runtime from Azure Key Vault using `EXT_CCP_KEY_VAULT_SECRET_NAME`. The `OpenIDClient` in [`swo_aws_extension/swo/openid/client.py`](../../swo_aws_extension/swo/openid/client.py) handles token refresh automatically.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_CLOUD_ORCHESTRATOR_API_BASE_URL` | Base URL for the Cloud Orchestrator API |
| `EXT_CCP_OAUTH_URL` | OAuth token endpoint (Azure AD) |
| `EXT_CCP_CLIENT_ID` | OAuth client ID |
| `EXT_CCP_KEY_VAULT_SECRET_NAME` | Azure Key Vault secret name holding the client secret |
| `EXT_AWS_OPENID_SCOPE` | OAuth scope for Cloud Orchestrator requests |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Check Bootstrap Role | `GET` | `/api/v1/bootstrap-role/check?target_account_id={id}` | Returns `{"deployed": true/false, ...}` for the target AWS account |
| Onboard Customer | `POST` | `/api/v1/marketplace/onboard` | Triggers onboarding and returns `{"execution_arn": "..."}` |
| Upgrade Customer | `POST` | `/api/v1/marketplace/upgrade` | Upgrades an account already onboarded and returns `{"executions": [{"execution_arn": "...", "deployment_id": "..."}, ...]}`, one execution per deployment of the account; used by the migration sync job |
| Get Deployment Status | `GET` | `/api/v1/deployments/execution-arn/{execution_arn}` | Returns `{"status": "succeeded/failed/running/pending"}` |

The upgrade payload only carries the customer SCU and the master payer id, because Cloud Orchestrator already holds the migrated account:

```json
{
  "scu": "US-SCU-999999",
  "master_payer_id": "987654321098"
}
```

Unlike onboard, the upgrade returns one execution per deployment of the account:

```json
{
  "executions": [
    {"execution_arn": "arn:aws:states:eu-west-1:123456789012:execution:deployment-1155d5f6:execution-54b05eea", "deployment_id": "f54e1c4b-3d90-4489-8ec6-f2b1157daf3b"},
    {"execution_arn": "arn:aws:states:eu-west-1:123456789012:execution:deployment-bf570ae0:execution-789355e7", "deployment_id": "5fb1a5e9-2678-4cd1-92f0-830559483b4d"}
  ]
}
```

The extension stores every `execution_arn` comma-separated in the single `executionArn` fulfillment parameter of the agreement and polls each ARN with Get Deployment Status on every run: the upgrade is complete once all the executions succeeded, the row fails when any execution failed, and the row is checked again while any execution is pending. A single ARN stored by an earlier version is read as a one-item list.

## Logging

The client logs every request at INFO, with the method, the URL and the payload. It logs every response at INFO, with the status and the body. This applies to all the endpoints.

## Error handling

Every failed call raises a subclass of `CloudOrchestratorError` from [`swo_aws_extension/swo/cloud_orchestrator/errors.py`](../../swo_aws_extension/swo/cloud_orchestrator/errors.py). The error keeps the operation, the method, the endpoint, the payload, the HTTP status and the response body. It exposes them as follows:

- `title`: the failed operation, for example `Cloud Orchestrator upgrade failed`.
- `message`: one line with the reason, the request, the status and the response, cut to about 500 characters. For example: `Cloud Orchestrator upgrade failed: response has an empty 'executions' list (POST api/v1/marketplace/upgrade, HTTP 200, response: {"executions": []})`.
- `facts`: the operation, the request, the payload, the HTTP status and the response, cut to about 2000 characters, for a Teams fact set.

| Error | Raised when |
| --- | --- |
| `CloudOrchestratorHttpError` | The response status is not 2xx |
| `CloudOrchestratorNotFoundError` | The response status is 404. It is a subclass of `CloudOrchestratorHttpError` |
| `CloudOrchestratorConnectionError` | The request does not complete, for example on a timeout or a refused connection |
| `CloudOrchestratorAuthError` | The client cannot get the OpenID access token |
| `CloudOrchestratorEmptyResponseError` | A 2xx response has an empty body |
| `CloudOrchestratorInvalidJsonError` | A 2xx response body is not valid JSON |
| `CloudOrchestratorUnexpectedResponseError` | The body is valid JSON but not an object, or it breaks the response contract of the endpoint |

Response contract of each endpoint:

| Operation | Contract |
| --- | --- |
| Check Bootstrap Role | `deployed` is a boolean |
| Onboard Customer | `execution_arn` is a non-empty string |
| Upgrade Customer | `executions` is a non-empty list, and every execution has a non-empty `execution_arn` string |
| Get Deployment Status | `status` is one of `succeeded`, `failed`, `running` or `pending`, in any case |

The client URL-encodes the `target_account_id` and the `execution_arn` path values.

The callers handle the error as follows:

- The migration sync job writes `message` to the `Error` field of the Airtable row and keeps the row `Completed`, so the next run tries the row again. It sends one Teams error card per failed call, and the run summary lists the row.
- The Onboard Services and Check Onboard Status steps put `message` in the error email details and send one Teams error card per failed call.
- The Check Customer Roles and Deploy Customer Roles steps stop with `title` and `message`. The base step sends that stop to Teams.
- The customer roles querying processor logs `message` at WARNING and checks the roles again on the next cycle.

The Teams error card holds the order id and the facts. The extension sends each card once per order id and error, because the pipeline processor meets the same error on every cycle.

## Code Reference

Client: [`swo_aws_extension/swo/cloud_orchestrator/client.py`](../../swo_aws_extension/swo/cloud_orchestrator/client.py)
