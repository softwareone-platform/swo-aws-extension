# Confluence

Attaches generated billing journals and reports to internal Confluence workspace pages. Used by the pending-orders reporting job to upload Excel files directly to a target Confluence page.

## Authentication

Basic Authentication using a service account username and a Personal Access Token (PAT). The Atlassian Python SDK handles the `Authorization: Basic <base64(user:token)>` header automatically when `cloud=True` is set.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_CONFLUENCE_BASE_URL` | Base URL of the Confluence instance |
| `EXT_CONFLUENCE_USER` | Service account email address |
| `EXT_CONFLUENCE_TOKEN` | Atlassian Personal Access Token |
| `EXT_PENDING_ORDERS_INFORMATION_REPORT_PAGE_ID` | Confluence page ID where pending-orders reports are attached |

## Operations

| Operation | SDK Method | Endpoint | Description |
| --- | --- | --- | --- |
| Attach Document | `Confluence.attach_content(...)` | `POST /rest/api/content/{page_id}/child/attachment` | Uploads binary content as a `multipart/form-data` attachment to the specified page |

The `ConfluenceClient.attach_content()` method returns `True` on success and `False` on any HTTP or connection error, logging the exception without re-raising.

## Code Reference

Client: [`swo_aws_extension/swo/confluence_client.py`](../../swo_aws_extension/swo/confluence_client.py)
