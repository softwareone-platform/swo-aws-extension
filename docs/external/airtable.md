# Airtable

Provides access to the per-product Airtable bases used by repository-specific
flows.

## Authentication

Workspace-scoped Airtable personal access token issued from the shared Airtable
service account. DevOps provisions and rotates the token, and it reaches the
extension through the `AirTableApiToken` Helm secret; a rotation is a secret
swap only, with no manifest changes.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_AIRTABLE_API_TOKEN` | Shared service-account Airtable token used by repository-specific flows |
| `EXT_AIRTABLE_BASES` | Per-product Airtable base mapping (`{"PRD-...":"app..."}`); the base is resolved per AWS product id |
