from io import BytesIO

import pytest
from requests import HTTPError

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.billing.billing_invoice_attachment_creator import (
    BillingInvoiceAttachmentCreator,
)


@pytest.fixture
def aws_client(mocker):
    return mocker.create_autospec(AWSClient, instance=True)


@pytest.fixture
def billing_api_client(mocker):
    # BillingClient.journal is set in __init__ and its attachments(id).upload chain is
    # resolved dynamically, so it cannot be autospecced; a plain mock is required here.
    return mocker.MagicMock()


@pytest.fixture
def creator(aws_client, billing_api_client):
    return BillingInvoiceAttachmentCreator(aws_client, billing_api_client)


def test_create_for_journal_uploads_invoice_pdf(creator, aws_client, billing_api_client):
    aws_client.download_invoice_pdf.return_value = b"invoice-pdf"

    result = creator.create_for_journal("JRN-1", {"INV-001"})

    assert (result.uploaded_invoice_ids, result.failed_invoice_ids) == ({"INV-001"}, set())
    aws_client.download_invoice_pdf.assert_called_once_with("INV-001")
    billing_api_client.journal.attachments.assert_called_once_with("JRN-1")
    upload = billing_api_client.journal.attachments.return_value.upload
    upload.assert_called_once()
    upload_kwargs = upload.call_args.kwargs
    assert upload_kwargs["filename"] == "AWS-Invoice-INV-001.pdf"
    assert upload_kwargs["mimetype"] == "application/pdf"
    assert isinstance(upload_kwargs["file"], BytesIO)
    assert upload_kwargs["file"].getvalue() == b"invoice-pdf"


def test_create_for_journal_continues_after_failure(creator, aws_client, billing_api_client):
    aws_client.download_invoice_pdf.side_effect = [AWSError("AWS failure"), b"invoice-pdf"]
    upload = billing_api_client.journal.attachments.return_value.upload

    result = creator.create_for_journal("JRN-1", {"INV-001", "INV-002"})

    assert result.failed_invoice_ids == {"INV-001"}
    assert result.uploaded_invoice_ids == {"INV-002"}
    assert aws_client.download_invoice_pdf.call_count == 2
    billing_api_client.journal.attachments.assert_called_once_with("JRN-1")
    upload.assert_called_once()
    assert upload.call_args.kwargs["filename"] == "AWS-Invoice-INV-002.pdf"


def test_create_for_journal_records_upload_failure(creator, aws_client, billing_api_client):
    aws_client.download_invoice_pdf.return_value = b"invoice-pdf"
    upload = billing_api_client.journal.attachments.return_value.upload
    upload.side_effect = HTTPError("Upload failed")

    result = creator.create_for_journal("JRN-1", {"INV-001"})

    assert result.failed_invoice_ids == {"INV-001"}
    assert result.uploaded_invoice_ids == set()


def test_create_for_journal_records_download_failure(creator, aws_client, billing_api_client):
    aws_client.download_invoice_pdf.side_effect = AWSError("Invoice PDF URL is missing")
    upload = billing_api_client.journal.attachments.return_value.upload

    result = creator.create_for_journal("JRN-1", {"INV-001"})

    assert result.failed_invoice_ids == {"INV-001"}
    assert result.uploaded_invoice_ids == set()
    upload.assert_not_called()


def test_create_for_journal_with_no_invoices_does_nothing(creator, aws_client):
    result = creator.create_for_journal("JRN-1", set())

    assert result.uploaded_invoice_ids == set()
    assert result.failed_invoice_ids == set()
    aws_client.download_invoice_pdf.assert_not_called()
