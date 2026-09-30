# Documentation

This repository follows the shared documentation standard:

- [standards/documentation.md](https://github.com/softwareone-platform/mpt-extension-skills/blob/main/standards/documentation.md)

This file documents repository-specific documentation rules only.

## Repository Rules

- `README.md` must stay short and act as the main human entry point.
- `AGENTS.md` must stay operational and tell AI agents which files to read first.
- Topic-specific behavior must live in the matching file under [`docs/`](.).
- `.github/copilot-instructions.md` must remain a thin adapter that points back to [`AGENTS.md`](../AGENTS.md).
- When runtime, testing, migration, or setup behavior changes, update the corresponding document in the same change.

## Current Documentation Map

- [`README.md`](../README.md): human entry point, overview, quick start, and documentation map
- [`AGENTS.md`](../AGENTS.md): AI entry point and reading order
- [`deployment.md`](deployment.md): runtime configuration and deployment model
- [`contributing.md`](contributing.md): repository-specific development workflow
- [`testing.md`](testing.md): testing strategy and command mapping
- [`migrations.md`](migrations.md): migration workflow and migration-specific constraints
- [`external-integrations.md`](external-integrations.md): index of all external services and APIs
- [`external/cloud-orchestrator.md`](external/cloud-orchestrator.md): Cloud Orchestrator API
- [`external/ccp.md`](external/ccp.md): CCP Platform (OpenID secret rotation)
- [`external/service-now.md`](external/service-now.md): Service-Now CRM ticketing
- [`external/finops.md`](external/finops.md): FinOps FFC Operations API
- [`external/cco.md`](external/cco.md): CCO API (Contract Creation Online)
- [`external/service-provisioning.md`](external/service-provisioning.md): Services Provisioning API
- [`external/azure-blob-storage.md`](external/azure-blob-storage.md): Azure Blob Storage
- [`external/confluence.md`](external/confluence.md): Confluence API
- [`external/ms-teams.md`](external/ms-teams.md): MS Teams notifications
- [`external/aws-ses.md`](external/aws-ses.md): AWS SES email

## Documentation Change Rule

When documentation changes, prefer updating the smallest relevant document instead of creating overlapping summary files.
