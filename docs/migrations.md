# Migrations

Shared migration knowledge lives in:

- [knowledge/migrations.md](https://github.com/softwareone-platform/mpt-extension-skills/blob/main/knowledge/migrations.md)
- [knowledge/make-targets.md](https://github.com/softwareone-platform/mpt-extension-skills/blob/main/knowledge/make-targets.md)

This file documents repository-specific migration behavior only.

## Migration Files

Repository migration scripts live in [`migrations/`](../migrations).

This repository uses the standard migration workflow and standard make-based command wiring used across related repositories. Use the shared migration knowledge above as the primary reference.

## Repository-Specific Constraints

- Migration commands are exposed through [`make/migrations.mk`](../make/migrations.mk) and run `mpt-service-cli migrate` inside the Docker-based app container.
- Repository job and billing flows under [`swo_aws_extension/flows/jobs/`](../swo_aws_extension/flows/jobs) are business workflows, not `mpt-service-cli` migrations.
- Changes to reporting, billing journal generation, or querying logic do not automatically require a new schema or data migration.

## When To Update This Document

Update this file when the repository changes:

- migration file locations
- migration command entry points
- required execution order
- rollout or safety constraints specific to this repository
