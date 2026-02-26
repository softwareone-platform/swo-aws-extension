from azure.storage.blob import BlobClient

from swo_aws_extension.swo.azure_blob_uploader import AzureBlobUploader

MODULE = "swo_aws_extension.swo.azure_blob_uploader"


def test_upload_and_get_sas_url(mocker):
    mock_blob_service_client_cls = mocker.patch(f"{MODULE}.BlobServiceClient", autospec=True)
    mock_service_client = mock_blob_service_client_cls.from_connection_string.return_value
    mock_service_client.account_name = "test_account"
    mock_service_client.credential.account_key = "test_key"
    mock_blob_client = mocker.MagicMock(spec=BlobClient)
    mock_blob_client.url = "https://test.blob.core.windows.net/test-container/report.xlsx"
    mock_service_client.get_blob_client.return_value = mock_blob_client
    mocker.patch(f"{MODULE}.generate_blob_sas", autospec=True, return_value="fake-sas")
    connection_string = "DefaultEndpointsProtocol=https;AccountName=test"
    container_name = "test-container"
    sas_expiry_days = 7
    uploader = AzureBlobUploader(
        connection_string=connection_string,
        container_name=container_name,
        sas_expiry_days=sas_expiry_days,
    )

    result = uploader.upload_and_get_sas_url(b"data", "report.xlsx")

    mock_blob_service_client_cls.from_connection_string.assert_called_once_with(connection_string)
    mock_service_client.get_blob_client.assert_called_once_with(
        container=container_name, blob="report.xlsx"
    )
    mock_blob_client.upload_blob.assert_called_once_with(b"data", overwrite=True)
    assert result == "https://test.blob.core.windows.net/test-container/report.xlsx?fake-sas"
