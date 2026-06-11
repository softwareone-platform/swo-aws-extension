# External Integrations

This document is the index of all external services and APIs integrated with the AWS extension.

Each integration document covers: purpose, authentication mechanism, required environment variables, and available operations.

## Integrations

| Service | Purpose | Auth Mechanism | Document |
| --- | --- | --- | --- |
| [Cloud Orchestrator](external/cloud-orchestrator.md) | AWS customer onboarding, bootstrap role validation, deployment status | OAuth 2.0 (OpenID Bearer) | [cloud-orchestrator.md](external/cloud-orchestrator.md) |
| [CCP Platform](external/ccp.md) | Monthly OpenID client secret rotation via Azure AD | OAuth 2.0 Client Credentials | [ccp.md](external/ccp.md) |
| [Service-Now (CRM)](external/service-now.md) | Customer service request creation and tracking | OAuth 2.0 Client Credentials | [service-now.md](external/service-now.md) |
| [FinOps (FFC)](external/finops.md) | Billing entitlement and datasource management | Self-signed JWT (HS256) | [finops.md](external/finops.md) |
| [CCO API](external/cco.md) | Contract registration in Navision | OAuth 2.0 Client Credentials | [cco.md](external/cco.md) |
| [Service Provisioning](external/service-provisioning.md) | Customer service onboarding from CCO contracts | OAuth 2.0 Client Credentials | [service-provisioning.md](external/service-provisioning.md) |
| [Azure Blob Storage](external/azure-blob-storage.md) | Report upload and SAS URL generation | Azure Storage Connection String | [azure-blob-storage.md](external/azure-blob-storage.md) |
| [Confluence](external/confluence.md) | Billing report attachment to Confluence pages | Basic Auth (username + API token) | [confluence.md](external/confluence.md) |
| [MS Teams](external/ms-teams.md) | Internal operational notifications | Incoming Webhook (no auth) | [ms-teams.md](external/ms-teams.md) |
| [AWS SES](external/aws-ses.md) | Customer-facing email delivery | AWS Access Key + Secret Key | [aws-ses.md](external/aws-ses.md) |
| [Airtable](external/airtable.md) | FinOps entitlements table (per-agreement records) | Personal Access Token | [airtable.md](external/airtable.md) |

## Code Location

All integration clients live under [`swo_aws_extension/swo/`](../swo_aws_extension/swo), grouped by service name. The [`swo_aws_extension/swo/base_client.py`](../swo_aws_extension/swo/base_client.py) `OAuthSessionClient` is the shared base for OAuth 2.0 integrations.
