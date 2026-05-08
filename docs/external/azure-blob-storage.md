# Azure Blob Storage

Stores generated binary reports (billing Excel files, invitation reports) in Azure object storage and produces time-limited SAS URLs for secure external delivery to customers.

## Authentication

Authenticated via the Azure Python SDK using a full Storage Account Connection String. No bearer token flow is involved; the SDK derives credentials directly from `EXT_AZURE_STORAGE_CONNECTION_STRING`.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_AZURE_STORAGE_CONNECTION_STRING` | Full Azure Storage Account connection string |
| `EXT_AZURE_STORAGE_CONTAINER` | Root container name for uploaded blobs |
| `EXT_AZURE_STORAGE_SAS_EXPIRY_DAYS` | Expiry period in days for generated SAS tokens |
| `EXT_REPORT_INVITATIONS_FOLDER` | Blob folder path for invitation reports |
| `EXT_REPORT_BILLING_FOLDER` | Blob folder path for billing reports |

## Operations

| Operation | SDK Method | Description |
| --- | --- | --- |
| Upload Blob | `BlobClient.upload_blob(data, overwrite=True)` | Uploads binary data to the specified blob name, overwriting any existing blob |
| Generate SAS URL | `generate_blob_sas(...)` | Generates a read-only SAS URL valid for `EXT_AZURE_STORAGE_SAS_EXPIRY_DAYS` days |

The `AzureBlobUploader.upload_and_get_sas_url()` method combines both operations: it uploads the file and immediately returns the SAS URL.

## Code Reference

Client: [`swo_aws_extension/swo/azure_blob_uploader.py`](../../swo_aws_extension/swo/azure_blob_uploader.py)
