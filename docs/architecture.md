# Architecture

This document describes the structure, major components, boundaries, and layer
responsibilities of `swo-aws-extension`. For workflow, testing, deployment,
migrations, and integration details, see the dedicated documents linked below.

## Purpose

`swo-aws-extension` is a SoftwareOne Marketplace Platform (MPT) extension that
fulfils and validates AWS Marketplace orders: it provisions AWS accounts,
configures billing transfers and the APN program, raises CRM/CCP tickets, syncs
FinOps entitlements, and generates billing journals and reports.

It is built on the MPT Extension SDK and runs as the registered `swo.mpt.ext`
extension (`pyproject.toml` `[project.entry-points."swo.mpt.ext"]` ->
`swo_aws_extension.apps:ExtensionConfig`).

## Entry points

- `swo_aws_extension/apps.py` — Django `ExtensionConfig`; validates webhook
  secrets and the single AWS product ID on startup.
- `swo_aws_extension/extension.py` — registers the SDK extension hooks:
  - order fulfilment event listener (`orders`) -> `process_order_fulfillment`
  - order validation endpoint (`POST /v1/orders/validate`) ->
    `process_order_validation`
- `swo_aws_extension/management/commands/` — Django management commands used by
  the worker for background jobs (billing journals, reports, agreement,
  FinOps and AWS migration order sync).

## Layers

The runtime is organised as a pipeline-driven fulfilment flow:

1. **Entry layer** (`extension.py`) — receives order fulfilment events and
   validation requests from the platform.
2. **Orchestration** (`flows/fulfillment/base.py`) — `fulfill_order()` selects a
   pipeline by order type: purchase a new AWS environment, purchase an existing
   one, or terminate. Purchase orders carrying the vendor-only migration
   parameter are routed first to the dedicated migration pipeline, regardless
   of account type; regular purchase orders are unaffected. The migration
   pipeline reuses the existing steps with the migration templates: it
   validates the prefilled migration data, copies the fulfillment
   parameters the Migration Orders extension cannot set at order creation
   from the order's AWS Account Migration Airtable row (`ccoContractNumber`
   from `MPT CCO`, and the optional `supportDiscount` and `serviceDiscount`
   from `SWO support discount` and `SWO usage discount`; the mapping in
   `flows/steps/set_migration_fulfillment_parameters.py` is extended for new
   parameters), creates the billing transfer invitation and waits in
   querying until the MCoE team accepts it manually (a declined, canceled or
   expired invitation fails the order), configures the APN program and
   channel handshake, creates the migration CRM ticket
   (`crmOnboardTicketId`), creates the master payer subscription and
   completes the order. The existing CCO is reused, so no contract card or
   ERP job is created; a missing migration row or CCO keeps the order in
   processing and notifies Teams when `ccoContractNumber` is unset. Customer roles and services deployment are
   not executed. The FinOps entitlement is created afterwards by the FinOps
   synchronization job, as for regular orders.
3. **Pipelines and steps** (`flows/fulfillment/pipelines.py`, `flows/steps/`) —
   each pipeline is an ordered sequence of `BasePhaseStep` steps that create
   resources, poll status, raise tickets, and advance the order phase. Order
   data flows through the steps as an `InitialAWSContext` / `PurchaseContext`
   (`flows/order.py`).
4. **Validation** (`flows/validation/base.py`) — pre-fulfilment validation and
   parameter visibility/requirement rules driven by account type.
5. **Integration clients** (`aws/`, `swo/`, `airtable/`) — typed clients that
   wrap each external system behind a single boundary.
6. **Background jobs** (`flows/jobs/`) — reporting and sync work invoked by
   management commands, including billing journal generation.

## Major components

| Package | Responsibility |
|---|---|
| `swo_aws_extension/` | Extension config, runtime `config.py`, order `parameters.py`, `constants.py` |
| `swo_aws_extension/flows/` | Fulfilment orchestration, pipelines, steps, validation, order context |
| `swo_aws_extension/flows/jobs/` | Background jobs: billing journal, reports, FinOps entitlement sync, AWS migration order sync to Airtable (`migration_sync_processor.py`, run daily by `synchronize_migration_orders` over the rows in `Pending notify customer`, `Migration in progress` and `Completed`: mirrors the order status of each row and sets the acceptance date, the effective billing transfer start date once AWS reports the invitation accepted, the completion date or the failure reason (the order `statusNotes` message, falling back to its `error` message); when a completed row has a start date on or before the run date it also creates the ServiceNow ticket that tells the MCoE team the transfer is active, stores its id in the `crmMigrationTicketId` parameter of the agreement (checked first, so a retried row never gets a second ticket; the ticket helpers live in `migration_billing_transfer_ticket.py`) then launches the services onboarding in Cloud Orchestrator with the same payload as the `OnboardServices` fulfillment step (`migration_services_onboarding.py`), stores the execution ARN in the `executionArn` parameter of the agreement (checked first, so a retried row never onboards twice; the agreement read and write helpers live in `migration_agreement_parameters.py`) and checks the execution status: the row moves to `Services onboarded` only when the execution succeeded, stays `Completed` and is checked again on the next run while it is pending or running, and keeps `Completed` with the error detail when the ticket, the onboarding start or the execution fails, all in a single Airtable write per row; migrated customers keep their existing CCO and ERP project; the run report (`migration_sync_report.py`) is sent to Teams only when a row changed, a ticket or onboarding was created or a row failed, listing the changes and errors per order; a run with nothing to report is only logged) |
| `swo_aws_extension/processor/` | Chain-of-responsibility processors for querying AWS roles, handshakes, transfers |
| `swo_aws_extension/aws/` | `AWSClient` (boto3 AssumeRole, account/billing/CUR operations) |
| `swo_aws_extension/swo/` | External-service clients (CCP, CRM, FinOps, CCO, Cloud Orchestrator, MPT, Key Vault, Blob, notifications, OpenID) |
| `swo_aws_extension/airtable/` | Airtable tables: FinOps entitlements sync and AWS Account Migration |
| `swo_aws_extension/management/` | Django management commands run by the worker |
| `swo_aws_extension/utils/`, `file_builder/` | Shared helpers and ZIP/report file building |

The per-service API clients live under `swo_aws_extension/swo/`, grouped by
service (`mpt/`, `ccp/`, `cco/`, `crm_service/`, `finops/`, `cloud_orchestrator/`,
`rql/`, `notifications/`, …) on top of the shared `base_client.py`.

## External integrations

AWS (`aws/`), CCP, CRM service, FinOps, CCO, and Cloud Orchestrator (`swo/`),
the MPT API (`swo/mpt/`), Airtable (`airtable/`), Azure Key Vault and Blob
Storage, Confluence, and MS Teams / email notifications. See
[external-integrations.md](external-integrations.md) for endpoints, auth, and
setup expectations.

## Boundaries

- External systems are reached only through their client package; business flows
  and steps depend on those clients, not on raw HTTP or SDK calls.
- Order state is carried by the context objects in `flows/order.py`; steps read
  and update the context rather than passing ad-hoc arguments.
- Configuration is read through `config.py` / Django settings, not from the
  environment directly inside business logic.

## Deployment shape

Two workloads are deployed from `helm/swo-extension-aws`: an **api** workload
(webhooks and the validation endpoint) and a **worker** workload (background
jobs and CronJobs). The container image is built from the multi-stage
`Dockerfile` and started via the SDK entrypoint. See
[deployment.md](deployment.md) for configuration and runtime parameters.

## Related documentation

- [contributing.md](contributing.md) — development workflow and commands
- [testing.md](testing.md) — test strategy and execution
- [deployment.md](deployment.md) — deployment model and configuration
- [migrations.md](migrations.md) — migration workflow
- [external-integrations.md](external-integrations.md) — external systems and setup
