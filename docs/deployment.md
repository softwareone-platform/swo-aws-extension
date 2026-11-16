# Deployment

This document is the source of truth for runtime configuration referenced by local development and deployment flows.

## Deployment Model

The repository describes its workloads in [`deployment-manifest.yaml`](../deployment-manifest.yaml). The Azure DevOps build (`azure-pipelines.yml`) renders it into a Helm chart with the common templates of `ops-mpt-infra` (`helm/helm-init.yaml@ops-mpt-infra`, branch `releases/v1`) and publishes the chart as `helm/swo-extension-aws`. [`helm/swo-extension-aws/templates/`](../helm/swo-extension-aws/templates) holds only templates the common chart cannot express.

The chart contains:

- an API workload (Deployment and Service `swo-extension-aws-web-api`, plus the compatibility Service `swo-extension-aws-api` still used by the `/mpt-extension-aws-api/` route)
- a worker workload (`swo-extension-aws-worker`, a single event consumer)
- cron jobs `swo-extension-aws-<key>` for the commands `order_querying_processor`, `synchronize_agreements`, `refresh_ccp_openid_secret`, `generate_billing_journals`, `synchronize_finops_accounts`, `synchronize_migration_orders`, `create_invitations_report`, and `create_pending_orders_information_report`

All workloads run as the service account `swo-extension-aws-sa` with Azure workload identity.

## Configuration Source

Local Docker Compose reads `.env`.

Deployed workloads receive configuration through one config map and one secret, both named `swo-extension-aws`. Each `env` and `secrets` entry in the manifest maps an App Configuration key `swo-extension-aws/<logicalKey>` to the runtime variable used locally. The logical key is the variable name in lowerCamelCase (`EXT_CRM_CLIENT_SECRET` -> `extCrmClientSecret`); `APPLICATIONINSIGHTS_CONNECTION_STRING` comes from the shared key `applicationInsightsConnectionString`. Secret values must reach Helm base64-encoded (`base64encode` tag in App Configuration).

## Core Marketplace Settings

| Environment Variable | Default | Example | Description |
| --- | --- | --- | --- |
| `MPT_API_BASE_URL` | `http://localhost:8000` | `https://api.s1.show/public` | SoftwareOne Marketplace API base URL |
| `MPT_API_TOKEN` | - | `eyJhbGciOi...` | Marketplace API token |
| `MPT_PORTAL_BASE_URL` | `http://localhost:8000` | `https://portal.s1.show` | Marketplace portal base URL |
| `MPT_PRODUCTS_IDS` | `PRD-1111-1111` | `PRD-1111-1111` | AWS extension currently supports a single Marketplace product id |
| `MPT_NOTIFY_CATEGORIES` | - | `{"ORDERS":"NTC-XXXX-XXXX"}` | Marketplace notification category mapping |
| `MPT_ORDERS_API_POLLING_INTERVAL_SECS` | `120` | `60` | Order polling interval |
| `MPT_KEY_VAULT_NAME` | - | `https://mpt-key-vault-name.vault.azure.net/` | Azure Key Vault URL used to resolve secrets |
| `MPT_TOOL_STORAGE_TYPE` | `local` | `airtable` | `mpt-tool` storage backend |
| `MPT_TOOL_STORAGE_AIRTABLE_API_KEY` | - | `patXXXXXXXX` | Airtable API key for `mpt-tool` storage; carries the shared Airtable service-account token (App Configuration key `mptToolStorageAirtableApiKey`) |
| `MPT_TOOL_STORAGE_AIRTABLE_BASE_ID` | - | `appXXXXXXXX` | Airtable base id for `mpt-tool` storage |
| `MPT_TOOL_STORAGE_AIRTABLE_TABLE_NAME` | - | `MigrationTracking` | Airtable table for `mpt-tool` storage |

## AWS And Marketplace Integration Settings

| Environment Variable | Default | Example | Description |
| --- | --- | --- | --- |
| `EXT_AWS_REGION` | `us-east-1` | `us-east-1` | AWS region used by extension flows |
| `EXT_AWS_OPENID_SCOPE` | - | `urn://dev.aws.services.softwareone.com/.default` | AWS OpenID scope |
| `EXT_WEBHOOKS_SECRETS` | - | `{"PRD-1111-1111":"secret"}` | Per-product webhook secret mapping |
| `EXT_MANAGEMENT_ROLE` | - | `SoftwareOneManagementRole` | AWS management role name |
| `EXT_BILLING_ROLE` | - | `SoftwareOneBillingRole` | AWS billing role name |
| `EXT_ONBOARD_CUSTOMER_ROLE` | - | `SoftwareOneOnboardCustomerRole` | AWS onboarding role name |
| `EXT_APN_ROLE_NAME` | - | `APNIntegrationRole` | APN role name |
| `EXT_APN_ACCOUNT_ID` | - | `123456789012` | APN account id |
| `EXT_QUERYING_TIMEOUT_DAYS` | - | `4` | Querying timeout for AWS processing |
| `EXT_CUSTOMER_ROLES_QUERYING_TIMEOUT_DAYS` | - | `4` | Timeout for customer-role querying flows |
| `EXT_MINIMUM_MPA_THRESHOLD` | - | `1000` | Minimum MPA threshold used by business logic |

## Integration And Service Settings

| Environment Variable | Default | Example | Description |
| --- | --- | --- | --- |
| `EXT_CCP_CLIENT_ID` | - | `123456789` | CCP OAuth client id |
| `EXT_CCP_OAUTH_URL` | - | `https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token` | CCP OAuth endpoint |
| `EXT_CCP_OAUTH_SCOPE` | - | `api://scope` | CCP OAuth scope |
| `EXT_CCP_OAUTH_CREDENTIALS_SCOPE` | - | `api://scope/.default` | CCP credentials scope when configured |
| `EXT_CCP_API_BASE_URL` | - | `https://ccp.example` | CCP API base URL |
| `EXT_CCP_KEY_VAULT_SECRET_NAME` | - | `ccp-key-vault-secret-name` | Key Vault secret name for CCP credentials |
| `EXT_CRM_API_BASE_URL` | - | `https://crm.example` | CRM API base URL |
| `EXT_CRM_AUDIENCE` | - | `https://crm.example/audience` | CRM OAuth audience |
| `EXT_CRM_CLIENT_ID` | - | `client-id` | CRM OAuth client id |
| `EXT_CRM_CLIENT_SECRET` | - | `secret` | CRM OAuth client secret |
| `EXT_CRM_OAUTH_URL` | - | `https://crm.example/oauth/token` | CRM OAuth endpoint |
| `EXT_CCO_MANUFACTURER_CODE` | - | `SWOTS` | Manufacturer code used when creating CCO contracts |
| `EXT_CLOUD_ORCHESTRATOR_API_BASE_URL` | - | `https://cloud-orchestrator.example` | Cloud orchestrator API base URL |
| `EXT_FFC_OPERATIONS_API_BASE_URL` | - | `https://ext-xxxx-xxxx.ext.s1.show/ops/v1` | FinOps extension operations API base URL; requests are authenticated with `MPT_API_TOKEN` |
| `EXT_AIRTABLE_BASES` | - | `{"PRD-1111-1111":"app..."}` | Per-product Airtable base mapping |
| `EXT_AIRTABLE_ACCOUNT_MIGRATION_BASE_ID` | - | `appXXXXXXXX` | Airtable base holding the `AWS Account Migration` table (separate from the per-product bases); App Configuration key `extAirtableAccountMigrationBaseId`, set per deployment |
| `EXT_AIRTABLE_API_TOKEN` | - | `patXXXXXXXX` | Airtable token used by repository-specific flows; carries the shared Airtable service-account token (App Configuration key `extAirtableApiToken`, see [external/airtable.md](external/airtable.md)) |

## Reporting, Notifications, And Storage

| Environment Variable | Default | Example | Description |
| --- | --- | --- | --- |
| `EXT_AZURE_STORAGE_CONNECTION_STRING` | - | `DefaultEndpointsProtocol=...` | Azure Blob Storage connection string |
| `EXT_AZURE_STORAGE_CONTAINER` | - | `reports` | Azure Blob Storage container name |
| `EXT_AZURE_STORAGE_SAS_EXPIRY_DAYS` | - | `30` | SAS expiry days for generated files |
| `EXT_REPORT_INVITATIONS_FOLDER` | - | `invitations` | Blob folder for invitation reports |
| `EXT_REPORT_BILLING_FOLDER` | - | `billing` | Blob folder for billing reports |
| `EXT_PENDING_ORDERS_INFORMATION_REPORT_PAGE_ID` | - | `1234567890` | Confluence page id used by pending-orders reporting |
| `EXT_CONFLUENCE_BASE_URL` | - | `https://softwareone.atlassian.net/wiki` | Confluence base URL |
| `EXT_CONFLUENCE_USER` | - | `service.user@softwareone.com` | Confluence service user |
| `EXT_CONFLUENCE_TOKEN` | - | `token` | Confluence access token |
| `EXT_MSTEAMS_WEBHOOK_URL` | - | `https://...office.com/...` | Microsoft Teams webhook for notifications |
| `EXT_EMAIL_NOTIFICATIONS_ENABLED` | - | `true` | Enables email notification flows where configured |
| `EXT_EMAIL_NOTIFICATIONS_SENDER` | - | `noreply@example.com` | Sender address for email notifications |
| `EXT_DEPLOY_SERVICES_FEATURE_RECIPIENTS` | - | `ops@example.com` | Recipients for deploy-services notifications |
| `EXT_AWS_SES_CREDENTIALS` | - | `<json-or-secret-ref>` | AWS SES credentials |
| `EXT_AWS_SES_REGION` | - | `eu-west-1` | AWS SES region |

## Billing Journal Settings

| Environment Variable | Default | Example | Description |
| --- | --- | --- | --- |
| `EXT_BILLING_DISCOUNT_BASE` | `7` | `7` | Billing default discount for services |
| `EXT_BILLING_DISCOUNT_INCENTIVE` | `12` | `12` | Billing discount for incentive services |
| `EXT_BILLING_DISCOUNT_SUPPORT_ENTERPRISE` | `35` | `35` | Billing discount for enterprise support |
| `EXT_BILLING_DISCOUNT_TOLERANCE_RATE` | `1` | `1` | Billing provider discount tolerance rate |
| `EXT_PLS_CHARGE_PERCENTAGE` | - | `3` | PLS charge percentage used in billing journal generation |

## Observability And Azure Auth

| Environment Variable | Default | Example | Description |
| --- | --- | --- | --- |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | - | `InstrumentationKey=...` | Azure Application Insights connection string |
| `OTEL_SERVICE_NAME` | - | `Swo.Extensions.Aws` | Telemetry service name |
| `SERVICE_NAME` | `Swo.Extensions.SwoDefaultExtensions` | `Swo.Extensions.Aws` | Service name used by default settings |
| `AZURE_CLIENT_ID` | - | `client-id-guid` | Azure client id for Key Vault access |
| `AZURE_TENANT_ID` | - | `tenant-id-guid` | Azure tenant id |
| `AZURE_CLIENT_CERTIFICATE_PASSWORD` | - | `password` | Azure client certificate password |
| `AZURE_CLIENT_CERTIFICATE_PATH` | - | `/extension/cert.pfx` | Azure client certificate path |
| `AZURE_CLIENT_PASSWORD_PATH` | - | `/extension/secrets/cert-password` | Optional file path used to load certificate password |

## Repository Constraints

- The extension startup check in [`swo_aws_extension/apps.py`](../swo_aws_extension/apps.py) rejects multiple product ids.
- The `env` and `secrets` entries of [`deployment-manifest.yaml`](../deployment-manifest.yaml) are the best source for deployed variable names.
- If configuration behavior is unclear, document the current code path instead of inventing expected values.
