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
| Get Deployment Status | `GET` | `/api/v1/deployments/execution-arn/{execution_arn}` | Returns `{"status": "succeeded/failed/running"}` |

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

While the upgrade API is in development, the extension logs the upgrade request payload and the response status and body at INFO.

## Code Reference

Client: [`swo_aws_extension/swo/cloud_orchestrator/client.py`](../../swo_aws_extension/swo/cloud_orchestrator/client.py)
