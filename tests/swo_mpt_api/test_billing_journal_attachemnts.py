from swo_mpt_api import MPTAPIClient


def test_list_attachments(requests_mock, mpt_client):
    journal_id = "journal-id"
    attachments_data = [
        {"id": "attachment-1", "filename": "file1.pdf"},
        {"id": "attachment-2", "filename": "file2.pdf"},
    ]
    response_data = {
        "data": attachments_data,
        "$meta": {
            "pagination": {
                "total": 2,
                "limit": 10,
                "offset": 0,
            }
        },
    }
    requests_mock.get(
        f"https://localhost/v1/billing/journals/{journal_id}/attachments", json=response_data
    )
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.attachments(journal_id).all()
    assert result == attachments_data


def test_upload_attachment(requests_mock, mpt_client, tmp_path):
    journal_id = "journal-id"
    file_content = b"test file content"
    file_path = tmp_path / "test.pdf"
    file_path.write_bytes(file_content)
    response_data = {"id": "attachment-1", "filename": "test.pdf"}

    requests_mock.post(
        f"https://localhost/v1/billing/journals/{journal_id}/attachments",
        json=response_data,
        status_code=201,
    )
    api = MPTAPIClient(mpt_client)
    with file_path.open("rb", encoding="utf-8") as f:
        result = api.billing.journal.attachments(journal_id).upload(
            f, "application/pdf", "test.pdf"
        )
    assert result == response_data


def test_get_attachment(requests_mock, mpt_client):
    journal_id = "journal-id"
    attachment_id = "attachment-1"
    attachment_data = {"id": attachment_id, "filename": "file1.pdf"}
    response_data = {"data": attachment_data}
    requests_mock.get(
        f"https://localhost/v1/billing/journals/{journal_id}/attachments/{attachment_id}",
        json=response_data,
    )
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.attachments(journal_id).get(attachment_id)
    assert result == response_data


def test_delete_attachment(requests_mock, mpt_client):
    journal_id = "journal-id"
    attachment_id = "attachment-1"
    requests_mock.delete(
        f"https://localhost/v1/billing/journals/{journal_id}/attachments/{attachment_id}",
        status_code=204,
    )
    api = MPTAPIClient(mpt_client)
    api.billing.journal.attachments(journal_id).delete(attachment_id)
