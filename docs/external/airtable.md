# Airtable

Stores the **FinOps Entitlements** table that tracks per-agreement FinOps
entitlement records (status and usage date). The extension reads and writes
these records while synchronising FinOps entitlements during fulfilment and
background jobs.

## Authentication

Airtable Personal Access Token (PAT). The `FinOpsEntitlementsTable` builds a
`pyairtable` `Api` client with the token and opens the configured base/table.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_AIRTABLE_API_TOKEN` | Airtable Personal Access Token used by repository-specific flows |
| `EXT_AIRTABLE_BASES` | Per-product Airtable base mapping (`{"PRD-...":"app..."}`); the base is resolved per AWS product id |

The table name is `FinOps Entitlements`.

## Operations

| Operation | Description |
| --- | --- |
| Get by agreement | `get_by_agreement_id(agreement_id)` — returns the entitlement records for an agreement |
| Save | `save(record)` — creates a new entitlement record |
| Update status and usage date | `update_status_and_usage_date(...)` — updates an existing record |

Operations are performed through the `pyairtable` table API rather than direct
HTTP calls.

## Code Reference

- Table client: [`swo_aws_extension/airtable/finops_table.py`](../../swo_aws_extension/airtable/finops_table.py)
- Records/fields: [`swo_aws_extension/airtable/models.py`](../../swo_aws_extension/airtable/models.py)
- Used by: [`swo_aws_extension/flows/steps/finops_entitlement.py`](../../swo_aws_extension/flows/steps/finops_entitlement.py) and [`swo_aws_extension/flows/jobs/finops_entitlements_processor.py`](../../swo_aws_extension/flows/jobs/finops_entitlements_processor.py)
