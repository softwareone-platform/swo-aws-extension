# SoftwareONE AWS Marketplace Extension

`swo-aws-extension` is a SoftwareOne Marketplace extension for AWS Marketplace workflows.

The repository contains:

- a Django-based extension runtime
- Marketplace order validation and fulfillment flows
- AWS, CCP, CRM, and Marketplace integration clients
- operational commands for querying, synchronization, reporting, and billing journals
- a deployment manifest for the API, worker, and cron workloads

## Documentation

Start here:

- [AGENTS.md](AGENTS.md): entry point for AI agents
- [docs/deployment.md](docs/deployment.md): runtime configuration and deployment model
- [docs/contributing.md](docs/contributing.md): repository-specific development workflow
- [docs/testing.md](docs/testing.md): testing strategy and commands
- [docs/migrations.md](docs/migrations.md): migration workflow and migration-specific constraints
- [docs/documentation.md](docs/documentation.md): repository documentation rules

## Quick Start

Prerequisites:

- Docker with the `docker compose` plugin
- `make`

Recommended setup:

```bash
cp .env.sample .env
make build
make test
make run
```

The application runs on `http://localhost:8080`.

See [docs/deployment.md](docs/deployment.md) for runtime parameters and the Docker-based local execution context.

## Repository Layout

- [`swo_aws_extension/`](swo_aws_extension): extension package and business flows
- [`tests/`](tests): pytest suite
- [`make/`](make): modular make targets
- [`migrations/`](migrations): `mpt-service-cli` migration scripts
- [`deployment-manifest.yaml`](deployment-manifest.yaml): deployment manifest rendered with the common Helm templates
- [`helm/swo-extension-aws/`](helm/swo-extension-aws): custom Helm templates added to the generated chart

## Common Commands

```bash
make build
make run
make test
make check
make check-all
make shell
```
