# Cloud Orchestrator

Manages AWS customer onboarding processes and bootstrap role deployments. The extension uses this API to trigger customer onboarding, verify bootstrap role readiness, and poll deployment execution status.

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
| Get Deployment Status | `GET` | `/api/v1/deployments/execution-arn/{execution_arn}` | Returns `{"status": "succeeded/failed/running"}` |

## Code Reference

Client: [`swo_aws_extension/swo/cloud_orchestrator/client.py`](../../swo_aws_extension/swo/cloud_orchestrator/client.py)
