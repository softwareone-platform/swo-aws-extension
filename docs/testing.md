# Testing

Shared unit-test rules live in [unittests.md](https://github.com/softwareone-platform/mpt-extension-skills/blob/main/standards/unittests.md).

Shared build and target knowledge also applies:

- [knowledge/build-and-checks.md](https://github.com/softwareone-platform/mpt-extension-skills/blob/main/knowledge/build-and-checks.md)
- [knowledge/make-targets.md](https://github.com/softwareone-platform/mpt-extension-skills/blob/main/knowledge/make-targets.md)

This file documents repository-specific testing behavior.

## Test Scope

The repository currently has stable coverage in these areas:

- extension registration and startup checks in [`tests/test_extension.py`](../tests/test_extension.py), [`tests/test_initializer.py`](../tests/test_initializer.py), and Django settings under [`tests/django/`](../tests/django)
- AWS client and configuration behavior in [`tests/aws/`](../tests/aws)
- fulfillment, jobs, steps, and validation flows in [`tests/flows/`](../tests/flows)
- management commands and helpers in [`tests/management/`](../tests/management) and [`tests/commands/`](../tests/commands)
- Marketplace, CCP, CRM, FinOps, notification, and query-builder integrations under [`tests/swo/`](../tests/swo), [`tests/swo_mpt_api/`](../tests/swo_mpt_api), [`tests/swo_ccp_client/`](../tests/swo_ccp_client), [`tests/swo_crm_service_client/`](../tests/swo_crm_service_client), [`tests/swo_finops_client/`](../tests/swo_finops_client), and [`tests/swo_rql/`](../tests/swo_rql)
- Airtable, file-builder, processor, and utility behavior in [`tests/airtable/`](../tests/airtable), [`tests/file_builder/`](../tests/file_builder), [`tests/processor/`](../tests/processor), and [`tests/utils/`](../tests/utils)

## Commands

Use the repository make targets:

```bash
make test
make check
make check-all
```

Repository command mapping:

- `make test` runs `pytest`
- `make check` runs `ruff format --check`, `ruff check`, `flake8`, and `uv lock --check`
- `make check-all` runs both checks and tests

The CI workflow in [`.github/workflows/pr-build-merge.yml`](../.github/workflows/pr-build-merge.yml) uses the same `make build` and `make check-all` flow.

## Pytest Configuration

Repository-specific test settings come from [`pyproject.toml`](../pyproject.toml):

- tests are discovered under `tests`
- `pythonpath` includes the repository root
- coverage is collected for the repository codebase and omits `tests/**`
- `DJANGO_SETTINGS_MODULE` is `tests.django.settings`
- tests run with `--import-mode=importlib`

## Writing Tests

Repository-specific guidance:

- prefer existing fixtures from [`tests/conftest.py`](../tests/conftest.py) and domain-specific `conftest.py` files under `tests/`
- add or update tests next to the affected domain area instead of creating catch-all test files
- keep external service calls mocked; do not make live AWS, Marketplace, CCP, CRM, FinOps, Airtable, Confluence, or notification calls in tests
- cover management command behavior in [`tests/management/commands/`](../tests/management/commands) when changing operational command entry points
- cover billing journal behavior in [`tests/flows/jobs/billing_journal/`](../tests/flows/jobs/billing_journal) when changing billing exports, discounts, or line processing

## When Tests Are Required

Add or update tests when a change modifies:

- extension startup or webhook handling
- validation behavior
- fulfillment behavior
- querying or background job behavior
- billing journal generation
- management command behavior
- AWS, CCP, CRM, FinOps, Airtable, storage, or notification integration logic

If a change only affects documentation, tests are not required.
