# CCP Platform

The CCP Platform is used exclusively to rotate the OpenID client secret that expires on a monthly basis. The extension calls the CCP API to retrieve a fresh `clientSecret`, then stores it in Azure Key Vault for use by the `OpenIDClient`.

## Authentication

OAuth 2.0 Client Credentials. The extension authenticates against the CCP OAuth endpoint using `EXT_CCP_OAUTH_CREDENTIALS_SCOPE` (a different scope than the one used for Cloud Orchestrator).

```http
POST <EXT_CCP_OAUTH_URL>
Content-Type: application/x-www-form-urlencoded

client_id=<EXT_CCP_CLIENT_ID>
client_secret=<CCP_KEY_VAULT_SECRET>
grant_type=client_credentials
scope=<EXT_CCP_OAUTH_CREDENTIALS_SCOPE>
```

The `client_secret` is retrieved from Azure Key Vault using `EXT_CCP_KEY_VAULT_SECRET_NAME` before each token request.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_CCP_API_BASE_URL` | Base URL of the CCP platform API |
| `EXT_CCP_OAUTH_URL` | OAuth token endpoint (Azure AD) |
| `EXT_CCP_CLIENT_ID` | OAuth client ID |
| `EXT_CCP_KEY_VAULT_SECRET_NAME` | Azure Key Vault secret name holding the client secret |
| `EXT_CCP_OAUTH_CREDENTIALS_SCOPE` | OAuth scope used for CCP secret retrieval |

## Operations

| Operation | Method | Endpoint | Description |
| --- | --- | --- | --- |
| Retrieve AD Secret | `GET` | `/process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1` | Returns `{"clientSecret": "..."}` for the given client ID |

## Secret Rotation Flow

1. `OpenIDClient` detects the current secret is expired or missing.
2. `CCPClient.refresh_secret()` acquires a temporary token using `EXT_CCP_OAUTH_CREDENTIALS_SCOPE`.
3. It calls the CCP secret endpoint to get the new `clientSecret`.
4. `KeyVaultManager.save_secret()` stores the new secret under `EXT_CCP_KEY_VAULT_SECRET_NAME`.
5. Subsequent OAuth token requests use the refreshed secret from Key Vault.

## Code Reference

Client: [`swo_aws_extension/swo/ccp/client.py`](../../swo_aws_extension/swo/ccp/client.py)
OpenID client: [`swo_aws_extension/swo/openid/client.py`](../../swo_aws_extension/swo/openid/client.py)
Key Vault manager: [`swo_aws_extension/swo/key_vault.py`](../../swo_aws_extension/swo/key_vault.py)
