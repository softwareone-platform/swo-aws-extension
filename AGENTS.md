# AGENTS.md

Working protocol for any task in this repository:

1. Identify the task type and select only the local repository files that are relevant to that task.
2. Read only those relevant local files before making changes.
3. If any selected local file references shared standards or shared operational guidance that are relevant to the same task, read those shared documents too before proceeding.
4. Treat repository-local documents as repository-specific additions, restrictions, or overrides to shared guidance.
5. If a repository-local rule conflicts with a shared rule, the local repository rule takes precedence.

When applicable, read the repository in this order::

1. [README.md](README.md) for the repository purpose, quick start, and documentation map.
2. [docs/deployment.md](docs/deployment.md) for runtime configuration and deployment-facing settings.
3. [docs/contributing.md](docs/contributing.md) for repository-specific workflow expectations.
4. [docs/testing.md](docs/testing.md) before changing code or tests.
5. [docs/migrations.md](docs/migrations.md) when a task mentions schema, data migrations, or `mpt-service-cli` migrations.
6. [docs/documentation.md](docs/documentation.md) when changing repository documentation.

Then inspect the code paths relevant to the task:

- [`swo_aws_extension/extension.py`](swo_aws_extension/extension.py): extension hooks, webhook validation endpoint, and event listeners
- [`swo_aws_extension/apps.py`](swo_aws_extension/apps.py): Django app setup and startup-time configuration validation
- [`swo_aws_extension/config.py`](swo_aws_extension/config.py) and [`swo_aws_extension/parameters.py`](swo_aws_extension/parameters.py): runtime configuration access and parameter definitions
- [`swo_aws_extension/flows/fulfillment/`](swo_aws_extension/flows/fulfillment): fulfillment workflows
- [`swo_aws_extension/flows/validation/`](swo_aws_extension/flows/validation): order validation workflows
- [`swo_aws_extension/flows/jobs/`](swo_aws_extension/flows/jobs): background jobs, billing journal generation, and reporting flows
- [`swo_aws_extension/processors/querying/`](swo_aws_extension/processors/querying): querying processors and AWS-related order processing logic
- [`swo_aws_extension/swo/`](swo_aws_extension/swo): Marketplace, CCP, CRM, FinOps, notification, and auth integrations
- [`swo_aws_extension/aws/`](swo_aws_extension/aws) and [`swo_aws_extension/airtable/`](swo_aws_extension/airtable): AWS and Airtable integration helpers
- [`swo_aws_extension/management/commands/`](swo_aws_extension/management/commands): operational and scheduled command entry points
- [`tests/`](tests): pytest coverage by domain area
- [`make/`](make): canonical local commands
- [`helm/swo-extension-aws/`](helm/swo-extension-aws): deployment manifests for API and worker workloads

Operational guidance:

- Prefer documented `make` targets over ad hoc Docker commands.
- Treat Docker Compose as the default local execution model.
- Keep repository policy in `docs/` and keep `.github/copilot-instructions.md` thin.
- Do not expand `README.md` into a full manual. Update the topic-specific file under `docs/`.
- Do not infer undocumented deployment or migration behavior. If the code does not make it explicit, document the current constraint instead of inventing rules.
