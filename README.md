[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=softwareone-platform_swo-aws-extension&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=softwareone-platform_swo-aws-extension)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=softwareone-platform_swo-aws-extension&metric=coverage)](https://sonarcloud.io/summary/new_code?id=softwareone-platform_swo-aws-extension)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

# SoftwareONE AWS Marketplace Extension

Extension integrates AWS Marketplace Extension with the SoftwareONE Marketplace

## Prerequisites

- Docker and Docker Compose plugin (`docker compose` CLI)
- `make`
- Valid `.env` file
- [CodeRabbit CLI](https://www.coderabbit.ai/cli) (optional. Used for running review check locally)


### Make targets overview

Common development workflows are wrapped in the `Makefile`. Run `make help` to see the list of available commands.

### How the Makefile works

The project uses a modular Makefile structure that organizes commands into logical groups:

- **Main Makefile** (`Makefile`): Entry point that automatically includes all `.mk` files from the `make/` directory
- **Modular includes** (`make/*.mk`): Commands are organized by category:
  - `common.mk` - Core development commands (build, test, format, etc.)
  - `repo.mk` - Repository management and dependency commands
  - `migrations.mk` - Database migration commands (Only available in extension repositories)
  - `external_tools.mk` - Integration with external tools


You can extend the Makefile with your own custom commands creating a `local.mk` file inside make folder. This file is
automatically ignored by git, so your personal commands won't affect other developers or appear in version control.


### Setup

Follow these steps to set up the development environment:

#### 1. Clone the repository

```bash
git clone <repository-url>
```
```bash
cd swo-aws-extension
```

#### 2. Create environment configuration

Copy the sample environment file and update it with your values:

```bash
cp .env.sample .env
```

Edit the `.env` file with your actual configuration values. See the [Configuration](#configuration) section for details on available variables.

#### 3. Build the Docker images

Build the development environment:

```bash
make build
```

This will create the Docker images with all required dependencies and the virtualenv.

#### 4. Verify the setup

Run the test suite to ensure everything is configured correctly:

```bash
make test
```

You're now ready to start developing! See [Running the service](#running-the-service) for next steps.


## Running the service

Before running, ensure your `.env` file is populated with real endpoints and tokens.

Start the app:

```bash
make run
```

The service will be available at `http://localhost:8080`.

Example `.env` snippet for real services:

```env
AZURE_CLIENT_ID=client-id-guid
AZURE_TENANT_ID=tenant-id-guid
AZURE_CLIENT_CERTIFICATE_PASSWORD=local-client-cert-pw
AZURE_CLIENT_CERTIFICATE_PATH=xxxxxxx.PFX
EXT_AWS_OPENID_SCOPE=urn://dev.aws.services.softwareone.com/.default
EXT_AWS_REGION=us-east-1
EXT_CCP_CLIENT_ID=123456789
EXT_CCP_KEY_VAULT_SECRET_NAME=ccp-key-vault-secret-name
EXT_CCP_OAUTH_SCOPE=api://scope
EXT_CCP_OAUTH_URL=https://login.microsoftonline.com/<tenant_id>/oauth2/v2.0/token
EXT_MSTEAMS_WEBHOOK_URL=https://whatever.webhook.office.com/webhookb2/<...>
EXT_WEBHOOKS_SECRETS={"PRD-1111-1111": "<webhook-secret-for-product>", "PRD-2222-2222": "<webhook-secret-for-product>"}
MPT_API_BASE_URL=https://api.s1.show/public
MPT_API_TOKEN=c0fdafd7-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MPT_KEY_VAULT_NAME=https://mpt-key-vault-name.vault.azure.net/
MPT_ORDERS_API_POLLING_INTERVAL_SECS=120
MPT_PORTAL_BASE_URL=https://portal.s1.show
MPT_PRODUCTS_IDS=PRD-1111-1111,PRD-2222-2222
MPT_TOOL_STORAGE_TYPE=airtable
MPT_TOOL_STORAGE_AIRTABLE_API_KEY=<fake-airtable-api-key>
MPT_TOOL_STORAGE_AIRTABLE_BASE_ID=<fake-storage-airtable-base-id>
MPT_TOOL_STORAGE_AIRTABLE_TABLE_NAME=<fake-storage-airtable-table-name>
```

`MPT_PRODUCTS_IDS` is a comma-separated list of SWO Marketplace Product identifiers.
For each product ID in the `MPT_PRODUCTS_IDS` list, define the corresponding entry in the `EXT_WEBHOOKS_SECRETS` JSON using the product ID as the key.


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

### Migration commands

The mpt-tool provides commands for managing database migrations:

```bash
make migrate-check                           # check migration status
make migrate-data                            # run data migrations
make migrate-schema                          # run schema migrations
make migrate-list                            # list available migrations
make migrate-new-data name=migration_id      # create a new data migration
make migrate-new-schema name=migration_id    # create a new schema migration
```


## Configuration

The following environment variables are typically set in `.env`. Docker Compose reads them when using the Make targets described above.

### Application

| Environment Variable                   | Default                 | Example                                   | Description                                                                               |
|----------------------------------------|-------------------------|-------------------------------------------|-------------------------------------------------------------------------------------------|
| `EXT_WEBHOOKS_SECRETS`                 | -                       | {"PRD-1111-1111": "123qweasd3432234"}     | Webhook secret of the Draft validation Webhook in SoftwareONE Marketplace for the product |
| `MPT_API_BASE_URL`                     | `http://localhost:8000` | `https://portal.softwareone.com/mpt`      | SoftwareONE Marketplace API URL                                                           |
| `MPT_API_TOKEN`                        | -                       | eyJhbGciOiJSUzI1N...                      | SoftwareONE Marketplace API Token                                                         |
| `MPT_NOTIFY_CATEGORIES`                | -                       | {"ORDERS": "NTC-XXXX-XXXX"}               | SoftwareONE Marketplace Notification Categories                                           |
| `MPT_PORTAL_BASE_URL`                  | `http://localhost:8000` | `https://portal.softwareone.com`          | SoftwareONE Marketplace Portal URL                                                        |
| `MPT_PRODUCTS_IDS`                     | PRD-1111-1111           | PRD-1234-1234,PRD-4321-4321               | Comma-separated list of SoftwareONE Marketplace Product ID                                |
| `MPT_TOOL_STORAGE_TYPE`                | `local`                 | `airtable`                                | Storage type for MPT tools (local or airtable)                                            |
| `MPT_TOOL_STORAGE_AIRTABLE_API_KEY`    | -                       | patXXXXXXXXXXXXXX                         | Airtable API key for MPT tool storage (required when storage type is airtable)            |
| `MPT_TOOL_STORAGE_AIRTABLE_BASE_ID`    | -                       | appXXXXXXXXXXXXXX                         | Airtable base ID for MPT tool storage (required when storage type is airtable)            |
| `MPT_TOOL_STORAGE_AIRTABLE_TABLE_NAME` | -                       | MigrationTracking                         | Airtable table name for MPT tool storage (required when storage type is airtable)         |


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
