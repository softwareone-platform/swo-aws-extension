# AGENTS.md

Working protocol for any task in this repository:

1. Identify the task type and select only the local repository files that are relevant to that task.
2. Read only those relevant local files before making changes.
3. If any selected local file references shared standards or shared operational guidance that are relevant to the same task, read those shared documents too before proceeding.
4. Treat repository-local documents as repository-specific additions, restrictions, or overrides to shared guidance.
5. If a repository-local rule conflicts with a shared rule, the local repository rule takes precedence.

When applicable, read the repository in this order:

1. [README.md](README.md) for the repository purpose, setup flow, make targets, and configuration overview.
2. [.github/copilot-instructions.md](.github/copilot-instructions.md) for repository-local Python, testing, and dependency rules.
3. [Makefile](Makefile) and the relevant files in [make/](make) for the supported local workflows and checks.
4. [compose.yaml](compose.yaml), [Dockerfile](Dockerfile), and [pyproject.toml](pyproject.toml) for runtime, dependency, and tooling constraints.
5. The relevant implementation packages under [swo_aws_extension/](swo_aws_extension) for the feature area you are changing.
6. The matching tests under [tests/](tests) before editing behavior, plus nearby fixtures or Django test settings when they affect the task.
7. [migrations/](migrations) and [helm/](helm) when the task touches data migrations, deployment, or runtime configuration.
8. [.github/workflows/](.github/workflows) when the change can affect CI, release, or required validation steps.

Before opening a PR or handing work back, run the narrowest meaningful validation first, then escalate to `make check-all` when the change scope warrants full verification.
