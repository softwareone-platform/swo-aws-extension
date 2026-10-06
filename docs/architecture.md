# Architecture

This document describes the structure, major components, boundaries, and layer
responsibilities of `swo-aws-extension`. For workflow, testing, deployment,
migrations, and integration details, see the dedicated documents linked below.

## Purpose

`swo-aws-extension` is a SoftwareOne Marketplace Platform (MPT) extension that
fulfils and validates AWS Marketplace orders: it provisions AWS accounts,
configures billing transfers and the APN program, raises CRM/CCP tickets, and
generates billing journals and reports.

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
  the worker for background jobs (billing journals, reports, agreement
  and AWS migration order sync).

## Layers

The runtime is organised as a pipeline-driven fulfilment flow:

1. **Entry layer** (`extension.py`) — receives order fulfilment events and
   validation requests from the platform.
2. **Orchestration** (`flows/fulfillment/base.py`) — selects a pipeline by
   order type: purchase a new AWS environment, purchase an existing one,
   terminate, or migrate. Purchase orders that carry the vendor-only migration
   parameter run the migration pipeline regardless of account type. The
   migration pipeline reuses the regular steps with migration templates. It
   starts from the data that the Migration Orders extension prefilled and the
   order's AWS Account Migration Airtable row. It creates the billing transfer
   invitation, waits for the MCoE team to accept it, configures the APN program
   and channel handshake, raises the migration CRM ticket and creates the
   master payer subscription. A channel handshake that times out does not stop
   the order: the pipeline continues to the CRM ticket and the subscription.
   The migrated account keeps its CCO and ERP
   project; customer roles and services are not deployed.
3. **Pipelines and steps** (`flows/fulfillment/pipelines.py`, `flows/steps/`) —
   each pipeline is an ordered sequence of `BasePhaseStep` steps that create
   resources, poll status, raise tickets, and advance the order phase. Order
   data flows through the steps as an `InitialAWSContext` / `PurchaseContext`
   (`flows/order.py`).
4. **Validation** (`flows/validation/base.py`) — pre-fulfilment validation and
   parameter visibility/requirement rules driven by account type. The
   `masterPayerID` parameter is hidden on every order except Purchase drafts
   with an existing account; migration orders show it because they skip draft
   validation and use the product default (`hidden: false`).
5. **Integration clients** (`aws/`, `swo/`, `airtable/`) — typed clients that
   wrap each external system behind a single boundary.
6. **Background jobs** (`flows/jobs/`, `billing/`, `swo/mpt/sync/`) — reporting
   and synchronization work that the worker runs through management commands:
   billing journal generation, reports, the AWS
   migration order sync and the agreement sync. The agreement sync validates
   the AWS responsibility transfer of each agreement and keeps one Marketplace
   subscription per linked AWS account with usage: it creates the missing
   subscriptions from Cost Explorer usage, starts an inactivity countdown on
   accounts without usage and terminates the subscription when the countdown
   expires.

## Major components

| Package | Responsibility |
|---|---|
| `swo_aws_extension/` | Extension config, runtime `config.py`, order `parameters.py`, `constants.py` |
| `swo_aws_extension/flows/` | Fulfilment orchestration, pipelines, steps, validation, order context |
| `swo_aws_extension/flows/jobs/` | Background jobs run by the worker: reports, MPT subscription sync for linked AWS accounts, and the daily AWS migration order sync. The migration sync mirrors each Marketplace migration order into its AWS Account Migration Airtable row. Once the billing transfer of a completed migration is effective, it moves the row to `Upgrading services`, creates the ServiceNow ticket for the MCoE team, launches the services upgrade of the migrated account in Cloud Orchestrator and stores both references in the agreement. The row moves to `Services onboarded` when the upgrade succeeds, and stays in `Upgrading services` with the error detail when a step fails. Each run reports its changes and errors to Teams. |
| `swo_aws_extension/billing/` | Billing journal generation, line processors, generators, models, and AWS invoice document attachment |
| `swo_aws_extension/billing/validation/` | Validation of every agreement billed by `generate_billing_journals`, run while its journal lines are generated and with no extra API calls: maps the AWS invoice summaries already fetched for the MPA to the cost price, list price and SPP discount, reads the discount parameters of the agreement, splits usage and support from the Cost Explorer metrics and derives the expected sales price with the same operations as the manual validation sheet (share of the SPP discount passed to the customer, support discount, PLS charge and discount, SPP returned on zero invoices). The result is compared with the agreement `SPP Summary` row within a tolerance (0.05 USD, converted to the agreement currency), written as the `Validation` sheet of the monthly billing report and summarised in a Teams warning when something is out of tolerance; in dry run it is only logged. A failure inside the validation is logged and never blocks the journal |
| `swo_aws_extension/processor/` | Chain-of-responsibility processors for querying AWS roles, handshakes, transfers |
| `swo_aws_extension/aws/` | `AWSClient` (boto3 AssumeRole, account/billing/CUR operations, Cost Explorer with dimension attributes, Invoicing summaries and invoice document retrieval) |
| `swo_aws_extension/swo/` | External-service clients (CCP, CRM, CCO, Cloud Orchestrator, MPT, Key Vault, Blob, notifications, OpenID) |
| `swo_aws_extension/airtable/` | Airtable tables: AWS Account Migration |
| `swo_aws_extension/management/` | Django management commands run by the worker |
| `swo_aws_extension/utils/`, `file_builder/` | Shared helpers and ZIP/report file building |

The per-service API clients live under `swo_aws_extension/swo/`, grouped by
service (`mpt/`, `ccp/`, `cco/`, `crm_service/`, `cloud_orchestrator/`,
`rql/`, `notifications/`, …) on top of the shared `base_client.py`.

## External integrations

AWS (`aws/`), CCP, CRM service, CCO, and Cloud Orchestrator (`swo/`),
the MPT API (`swo/mpt/`), Airtable, Azure Key Vault and Blob
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
