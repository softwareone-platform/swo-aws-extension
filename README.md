[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=softwareone-platform_swo-aws-extension&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=softwareone-platform_swo-aws-extension)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=softwareone-platform_swo-aws-extension&metric=coverage)](https://sonarcloud.io/summary/new_code?id=softwareone-platform_swo-aws-extension)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

# SoftwareONE AWS Marketplace Extension

Extension integrates AWS Marketplace Extension with the SoftwareONE Marketplace

## Prerequisites

- Docker and Docker Compose plugin (`docker compose` CLI)
- `make`
- Valid `.env` file
- Adobe credentials and authorizations JSON files in the project root
- [CodeRabbit CLI](https://www.coderabbit.ai/cli) (optional. Used for running review check locally)

Common development workflows are wrapped in the `makefile`:

- `make help` – list available commands
- `make bash` – start the app container and open a bash shell
- `make build` – build the application image for development
- `make check` – run code quality checks (ruff, flake8, lockfile check)
- `make check-all` – run checks and tests
- `make format` – apply formatting and import fixes
- `make down` – stop and remove containers
- `make review` –  check the code in the cli by running CodeRabbit
- `make run` – run the service
- `make shell` – open a Django shell inside the running app container
- `make test` – run the test suite with pytest

## Running tests

Tests run inside Docker using the dev configuration.

Run the full test suite:

```bash
make test
```

Pass additional arguments to pytest using the `args` variable:

```bash
make test args="-k test_extension -vv"
make test args="tests/flows/test_orders_flow.py"
```

## Running the service

### 1. Configuration files

In the project root, create and configure the following files.

#### Environment files

Start from the sample file:

```bash
cp .env.sample .env
```

Update `.env` with your values. This file is used by all Docker Compose configurations and the `make run` target.

### 2. Running

Run the service against real AWS and SoftwareONE Marketplace APIs. It uses `compose.yaml` and reads environment from `.env`.

Ensure:
- `.env` is populated with real endpoints and tokens.

Start the app:

```bash
make run
```

The service will be available at `http://localhost:8080`.

Example `.env` snippet for real services:

```env
MPT_PRODUCTS_IDS=PRD-1111-1111,PRD-2222-2222
EXT_WEBHOOKS_SECRETS={"PRD-1111-1111": "<webhook-secret-for-product>", "PRD-2222-2222": "<webhook-secret-for-product>"}
MPT_PORTAL_BASE_URL=https://portal.s1.show
MPT_API_BASE_URL=https://api.s1.show/public
MPT_API_TOKEN=c0fdafd7-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MPT_KEY_VAULT_NAME=https://mpt-key-vault-name.vault.azure.net/
MPT_ORDERS_API_POLLING_INTERVAL_SECS=120
EXT_AWS_OPENID_SCOPE=urn://dev.aws.services.softwareone.com/.default
EXT_AWS_REGION=us-east-1
EXT_CCP_CLIENT_ID=123456789
EXT_CCP_KEY_VAULT_SECRET_NAME=ccp-key-vault-secret-name
EXT_CCP_OAUTH_URL=https://login.microsoftonline.com/<tenant_id>/oauth2/v2.0/token
EXT_CCP_OAUTH_SCOPE=api://scope
EXT_MSTEAMS_WEBHOOK_URL=https://whatever.webhook.office.com/webhookb2/<...>
AZURE_CLIENT_ID=client-id-guid
AZURE_TENANT_ID=tenant-id-guid
AZURE_CLIENT_CERTIFICATE_PASSWORD=local-client-cert-pw
AZURE_CLIENT_CERTIFICATE_PATH=xxxxxxx.PFX
```

`MPT_PRODUCTS_IDS` is a comma-separated list of SWO Marketplace Product identifiers.
For each product ID in the `MPT_PRODUCTS_IDS` list, define the corresponding entry in the `WEBHOOKS_SECRETS` JSON using the product ID as the key.


## Developer utilities

Useful helper targets during development:

```bash
make bash      # open a bash shell in the app container
make check     # run ruff, flake8, and lockfile checks
make check-all # run checks and tests
make format    # auto-format code and imports
make review    # check the code in the cli by running CodeRabbit
make shell     # open a Django shell in the app container
```

## Configuration

The following environment variables are typically set in `.env`. Docker Compose reads them when using the Make targets described above.

### Application

| Environment Variable            | Default                 | Example                                 | Description                                                                               |
|---------------------------------|-------------------------|-----------------------------------------|-------------------------------------------------------------------------------------------|
| `EXT_WEBHOOKS_SECRETS`          | -                       | {"PRD-1111-1111": "123qweasd3432234"}   | Webhook secret of the Draft validation Webhook in SoftwareONE Marketplace for the product |
| `MPT_PRODUCTS_IDS`              | PRD-1111-1111           | PRD-1234-1234,PRD-4321-4321             | Comma-separated list of SoftwareONE Marketplace Product ID                                |
| `MPT_API_BASE_URL`              | `http://localhost:8000` | `https://portal.softwareone.com/mpt`    | SoftwareONE Marketplace API URL                                                           |
| `MPT_API_TOKEN`                 | -                       | eyJhbGciOiJSUzI1N...                    | SoftwareONE Marketplace API Token                                                         |
| `MPT_NOTIFY_CATEGORIES`         | -                       | {"ORDERS": "NTC-XXXX-XXXX"}             | SoftwareONE Marketplace Notification Categories                                           |


## Azure AppInsights

| Environment Variable                    | Default                     | Example                                                                                                                                                                                               | Description                                                                                                   |
|-----------------------------------------|-----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `SERVICE_NAME`                          | Swo.Extensions.Aws          | Swo.Extensions.Aws                                                                                                                                                                                    | Service name that is visible in the AppInsights logs                                                          |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | -                           | `InstrumentationKey=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx;IngestionEndpoint=https://westeurope-1.in.applicationinsights.azure.com/;LiveEndpoint=https://westeurope.livediagnostics.monitor.azure.com/` | Azure Application Insights connection string                                                                  |
| `LOGGING_ATTEMPT_GETTER`                | aws.utils.get_attempt_count | aws.utils.get_attempt_count                                                                                                                                                                           | Path to python function that retrieves order processing attempt to put it into the Azure Application Insights |

## Key Vault

| Environment Variable                  | Default | Example                                       | Description                                                                                   |
|---------------------------------------|---------|-----------------------------------------------|-----------------------------------------------------------------------------------------------|
| `MPT_KEY_VAULT_NAME`                  | -       | `https://mpt-key-vault-name.vault.azure.net/` | Azure Key Vault name                                                                          |
| `EXT_CCP_KEY_VAULT_SECRET_NAME`       | -       | ccp-key-vault-secret-name                     | Azure Key Vault secret name where CCP token is stored                                         |
| `EXT_CCP_OAUTH_SCOPE`                 | -       | api://scope                                   | Scope for CCP token authentication API request for authorization to retrieve token from CCP   |
| `AZURE_CLIENT_ID`                     | -       | azure-client-id-guid                          | Client ID for key vault                                                                       |
| `AZURE_TENANT_ID`                     | -       | azure-tenant-id-guid                          | Tenant ID for key vault                                                                       |
| `AZURE_CLIENT_CERTIFICATE_PASSWORD`   | -       | password                                      | Password for azure client certificate                                                         |
| `AZURE_CLIENT_CERTIFICATE_PATH`       | -       | /folder/abcdef.pfx                            | Path and file path to azure client certificate                                                |

## FinOps

| Environment Variable              | Default  | Example                              | Description       |
|-----------------------------------|----------|--------------------------------------|-------------------|
| `EXT_FFC_SUB`                     | -        | FTKN-1111-1111                       | FinOps subject    |
| `EXT_FFC_OPERATIONS_API_BASE_URL` | -        | `https://api.finops.s1.show/ops/v1/` | FinOps base URL   |
| `EXT_FFC_OPERATIONS_SECRET`       | -        | supersecret                          | FinOps secret     |

## Usage

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
