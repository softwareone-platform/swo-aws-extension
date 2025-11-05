[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=softwareone-platform_swo-aws-extension&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=softwareone-platform_swo-aws-extension)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=softwareone-platform_swo-aws-extension&metric=coverage)](https://sonarcloud.io/summary/new_code?id=softwareone-platform_swo-aws-extension)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

# SoftwareONE AWS Marketplace Extension

Extension integrates AWS Marketplace Extension with the SoftwareONE Marketplace

# Run tests

```
$ docker-compose build app_test
$ docker-compose run --service-ports app_test
```

# Local run using SoftwareONE Marketplace API

## Create configuration files

1. Create environment file

```
$ cp .env.sample .env
```

1. Setup parameters for `.env` file

```
MPT_PRODUCTS_IDS=PRD-1111-1111
MPT_PORTAL_BASE_URL=http://devmock:8000
MPT_API_BASE_URL=http://devmock:8000
MPT_API_TOKEN=<vendor-api-token>
MPT_ORDERS_API_POLLING_INTERVAL_SECS=120
EXT_WEBHOOKS_SECRETS={"PRD-1111-1111": "<super-jwt-secret>"}
EXT_MSTEAMS_WEBHOOK_URL=https://whatever.webhook.office.com/webhookb2/<...>
EXT_CCP_CLIENT_ID=123456789
EXT_AWS_OPENID_SCOPE=urn://dev.aws.services.softwareone.com/.default
EXT_CCP_OAUTH_URL=https://login.microsoftonline.com/<tenant_id>/oauth2/v2.0/token
EXT_AWS_REGION=us-east-1
```

`MPT_PRODUCTS_IDS` should be a comma-separated list of the SWO Marketplace Product identifiers
For each of the defined product id in the `MPT_PRODUCTS_IDS` list define `WEBHOOKS_SECRETS` json variables using product
ID as key.

```
EXT_WEBHOOKS_SECRETS={"PRD-1111-1111": "<webhook-secret-for-product>"}
```

Example of `.env` file

```
MPT_PRODUCTS_IDS=PRD-1111-1111
MPT_PORTAL_BASE_URL=http://devmock:8000
MPT_API_BASE_URL=http://devmock:8000
MPT_API_TOKEN=<vendor-api-token>
MPT_ORDERS_API_POLLING_INTERVAL_SECS=120
EXT_WEBHOOKS_SECRETS={"PRD-1111-1111": "<super-jwt-secret>"}
EXT_MSTEAMS_WEBHOOK_URL=https://whatever.webhook.office.com/webhookb2/<...>
EXT_CCP_CLIENT_ID=CCP Client ID
EXT_AWS_OPENID_SCOPE=urn://dev.aws.services.softwareone.com/.default
EXT_CCP_OAUTH_URL=https://login.microsoftonline.com/<tenant_id>/oauth2/v2.0/token
EXT_AWS_REGION=us-east-1
MPT_KEY_VAULT_NAME=https://mpt-key-vault-name.vault.azure.net/
EXT_CCP_KEY_VAULT_SECRET_NAME=ccp-key-vault-secret-name
EXT_CCP_OAUTH_SCOPE=api://scope
AZURE_CLIENT_ID=client-id-guid
AZURE_TENANT_ID=tenant-id-guid
AZURE_CLIENT_CERTIFICATE_PASSWORD=local-client-cert-pw
AZURE_CLIENT_CERTIFICATE_PATH=xxxxxxx.PFX
```

```


## Build and run extension

1. Build and run the extension
```

$ docker-compose build app
$ docker-compose run --service-ports app

```

# Configuration

## Application
| Environment Variable            | Default               | Example                               | Description                                                                               |
|---------------------------------|-----------------------|---------------------------------------|-------------------------------------------------------------------------------------------|
| `EXT_WEBHOOKS_SECRETS`          | -                     | {"PRD-1111-1111": "123qweasd3432234"} | Webhook secret of the Draft validation Webhook in SoftwareONE Marketplace for the product |
| `MPT_PRODUCTS_IDS`              | PRD-1111-1111         | PRD-1234-1234,PRD-4321-4321           | Comma-separated list of SoftwareONE Marketplace Product ID                                |
| `MPT_API_BASE_URL`              | http://localhost:8000 | https://portal.softwareone.com/mpt    | SoftwareONE Marketplace API URL                                                           |
| `MPT_API_TOKEN`                 | -                     | eyJhbGciOiJSUzI1N...                  | SoftwareONE Marketplace API Token                                                         |
| `MPT_NOTIFY_CATEGORIES`         | -                     | {"ORDERS": "NTC-XXXX-XXXX"}           | SoftwareONE Marketplace Notification Categories                                           |


## Azure AppInsights
| Environment Variable                    | Default                     | Example                                                                                                                                                                                             | Description                                                                                                   |
|-----------------------------------------|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `SERVICE_NAME`                          | Swo.Extensions.Aws          | Swo.Extensions.Aws                                                                                                                                                                                  | Service name that is visible in the AppInsights logs                                                          |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | -                           | InstrumentationKey=cf280af3-b686-40fd-8183-ec87468c12ba;IngestionEndpoint=https://westeurope-1.in.applicationinsights.azure.com/;LiveEndpoint=https://westeurope.livediagnostics.monitor.azure.com/ | Azure Application Insights connection string                                                                  |
| `LOGGING_ATTEMPT_GETTER`                | aws.utils.get_attempt_count | aws.utils.get_attempt_count                                                                                                                                                                         | Path to python function that retrieves order processing attempt to put it into the Azure Application Insights |

## Key Vault
| Environment Variable                  | Default | Example                                     | Description                                                                                   |
|---------------------------------------|---------|---------------------------------------------|-----------------------------------------------------------------------------------------------|
| `MPT_KEY_VAULT_NAME`                  | -       | https://mpt-key-vault-name.vault.azure.net/ | Azure Key Vault name                                                                          |
| `EXT_CCP_KEY_VAULT_SECRET_NAME`       | -       | ccp-key-vault-secret-name                   | Azure Key Vault secret name where CCP token is stored                                         |
| `EXT_CCP_OAUTH_SCOPE`                 | -       | api://scope                                 | Scope for CCP token authentication API request for authorization to retrieve token from CCP   |
| `AZURE_CLIENT_ID`                     | -       | azure-client-id-guid                        | Client ID for key vault                                                                       |
| `AZURE_TENANT_ID`                     | -       | azure-tenant-id-guid                        | Tenant ID for key vault                                                                       |
| `AZURE_CLIENT_CERTIFICATE_PASSWORD`   | -       | password                                    | Password for azure client certificate                                                         |
| `AZURE_CLIENT_CERTIFICATE_PATH`       | -       | /folder/abcdef.pfx                          | Path and file path to azure client certificate                                                |

## FinOps
| Environment Variable              | Default  | Example                            | Description       |
|-----------------------------------|----------|------------------------------------|-------------------|
| `EXT_FFC_SUB`                     | -        | FTKN-1111-1111                     | FinOps subject    |
| `EXT_FFC_OPERATIONS_API_BASE_URL` | -        | https://api.finops.s1.show/ops/v1/ | FinOps base URL   |
| `EXT_FFC_OPERATIONS_SECRET`       | -        | supersecret                        | FinOps secret     |

## USAGE
| Environment Variable                      | Default | Example | Description                               |
|-------------------------------------------|---------|---------|-------------------------------------------|
| `EXT_BILLING_DISCOUNT_BASE`               | 7       | 7       | Billing default discount for services     |
| `EXT_BILLING_DISCOUNT_INCENTIVE`          | 12      | 12      | Billing discount for incentivate services |
| `EXT_BILLING_DISCOUNT_SUPPORT_ENTERPRISE` | 35      | 35      | Billing discount for support enterprise   |
| `EXT_BILLING_DISCOUNT_TOLERANCE_RATE`     | 1       | 1       | Billing provider discount tolerance rate  |

## Other
| Environment Variable                   | Default | Example | Description                                                          |
|----------------------------------------|---------|---------|----------------------------------------------------------------------|
| `MPT_ORDERS_API_POLLING_INTERVAL_SECS` | 120     | 60      | Orders polling interval from the Software Marketplace API in seconds |

