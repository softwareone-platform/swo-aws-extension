import datetime as dt
import logging

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

logger = logging.getLogger(__name__)


class AzureBlobUploader:
    """Handles uploading files to Azure Blob Storage and generating SAS URLs."""

    def __init__(
        self,
        connection_string: str,
        container_name: str,
        sas_expiry_days: int,
    ):
        self.container_name = container_name
        self.sas_expiry_days = sas_expiry_days
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    def upload_and_get_sas_url(self, file_data: bytes, blob_name: str) -> str:
        """Uploads data and returns a SAS URL.

        Args:
            file_data: The binary data to upload.
            blob_name: The name of the blob in the container.

        Returns:
            A SAS URL for accessing the uploaded blob.
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name,
        )
        blob_client.upload_blob(file_data, overwrite=True)
        logger.info("Report uploaded to Azure Blob: %s/%s", self.container_name, blob_name)

        account_name = self.blob_service_client.account_name
        account_key = self.blob_service_client.credential.account_key
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=dt.datetime.now(dt.UTC) + dt.timedelta(days=self.sas_expiry_days),
        )
        return f"{blob_client.url}?{sas_token}"
