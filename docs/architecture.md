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
  the worker for background jobs (billing journals, reports, agreement and
  FinOps sync).

## Layers

The runtime is organised as a pipeline-driven fulfilment flow:

1. **Entry layer** (`extension.py`) — receives order fulfilment events and
   validation requests from the platform.
2. **Orchestration** (`flows/fulfillment/base.py`) — `fulfill_order()` selects a
   pipeline by order type: purchase a new AWS environment, purchase an existing
   one, or terminate.
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
| `swo_aws_extension/flows/jobs/` | Background jobs: billing journal, reports, FinOps entitlement sync |
| `swo_aws_extension/processors/` | Chain-of-responsibility processors for querying AWS roles, handshakes, transfers |
| `swo_aws_extension/aws/` | `AWSClient` (boto3 AssumeRole, account/billing/CUR operations) |
| `swo_aws_extension/swo/` | External-service clients (CCP, CRM, FinOps, CCO, Cloud Orchestrator, MPT, Key Vault, Blob, notifications, OpenID) |
| `swo_aws_extension/airtable/` | FinOps entitlements Airtable sync |
| `swo_aws_extension/management/` | Django management commands run by the worker |
| `swo_aws_extension/utils/`, `file_builder/` | Shared helpers and ZIP/report file building |

The repository also vendors several standalone client packages used by the
extension and reusable across repos: `swo_mpt_api`, `swo_ccp_client`,
`swo_crm_service_client`, `swo_finops_client`, and `swo_rql`.

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
