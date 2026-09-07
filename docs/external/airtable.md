# Airtable

Stores two tables used by the extension:

- **FinOps Entitlements** tracks per-agreement FinOps entitlement records
  (status and usage date). The extension reads and writes these records while
  synchronising FinOps entitlements during fulfilment and background jobs.
- **AWS Account Migration** holds the accounts to migrate to the AWS extension. It is
  the source of truth of the migration described in the AWS TDR Migration:
  operations load the import columns per batch, and the extensions manage the
  state-control columns (migration status, order data, dates, error detail).

## Authentication

Workspace-scoped Airtable personal access token issued from the shared Airtable
service account. DevOps provisions and rotates the token, and it reaches the
extension through the `AirTableApiToken` Helm secret; a rotation is a secret
swap only, with no manifest changes. Each table client builds a `pyairtable`
`Api` client with the token and opens the configured base/table.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_AIRTABLE_API_TOKEN` | Shared service-account Airtable token used by repository-specific flows |
| `EXT_AIRTABLE_BASES` | Per-product Airtable base mapping (`{"PRD-...":"app..."}`); the FinOps base is resolved per AWS product id |
| `EXT_AIRTABLE_ACCOUNT_MIGRATION_BASE_ID` | Base id of the dedicated `AWS Account Migration` base |

The `FinOps Entitlements` table lives in the per-product base. The
`AWS Account Migration` table lives in its own base, one per environment, so the
migration data stays separate from the master payer pool.

## FinOps Entitlements

| Operation | Description |
| --- | --- |
| Get by agreement | `get_by_agreement_id(agreement_id)` — returns the entitlement records for an agreement |
| Save | `save(record)` — creates or updates an entitlement record (depending on whether it is new) |
| Update status and usage date | `update_status_and_usage_date(...)` — updates an existing record |

## AWS Account Migration

The table must pre-exist. Operations load the import columns per batch (seller,
buyer, master payer, CCO, contact and support data); the extensions manage the
state-control columns (migration status, order data, dates, error detail). The
column names live in `AccountMigrationFields`, and `AccountMigrationStatus` /
`AccountMigrationOrderStatus` enumerate the dropdown values. The final column set is
still being agreed in the AWS TDR Migration, so treat the code as the source of
truth for the current layout.

| Operation | Description |
| --- | --- |
| Get by status | `get_by_status(status)` — returns the rows with the given migration status, in table order (use `AccountMigrationStatus.READY` for the pending rows) |
| Get by order | `get_by_order_id(order_id)` — returns the row linked to a Marketplace order, or `None` |
| Get by billing transfer start date | `get_by_billing_transfer_start_date(date)` — returns the rows whose billing transfer starts on the given ISO date |
| Save | `save(record)` — creates or updates a row (depending on whether it is new) |
| Update status | `update_status(record, status, error=None)` — sets the migration status and, optionally, the error detail |

Operations are performed through the `pyairtable` table API rather than direct
HTTP calls.

## Code Reference

- FinOps table client: [`swo_aws_extension/airtable/finops_table.py`](../../swo_aws_extension/airtable/finops_table.py)
- AWS Account Migration table client: [`swo_aws_extension/airtable/account_migration_table.py`](../../swo_aws_extension/airtable/account_migration_table.py)
- Records/fields: [`swo_aws_extension/airtable/models.py`](../../swo_aws_extension/airtable/models.py)
- Used by: [`swo_aws_extension/flows/steps/finops_entitlement.py`](../../swo_aws_extension/flows/steps/finops_entitlement.py) and [`swo_aws_extension/flows/jobs/finops_entitlements_processor.py`](../../swo_aws_extension/flows/jobs/finops_entitlements_processor.py); the AWS Account Migration table is consumed by the migration sync job and the Migration Orders extension
