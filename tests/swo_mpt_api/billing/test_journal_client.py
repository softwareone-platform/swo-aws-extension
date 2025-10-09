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
    with file_path.open("rb") as f:
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


def test_all_charges(requests_mock, mpt_client):
    journal_id = "journal-id"
    charges_data = [
        {"id": "charge-1", "amount": 100},
        {"id": "charge-2", "amount": 200},
    ]
    response_mock = {
        "$meta": {
            "pagination": {
                "total": 2,
                "limit": 10,
                "offset": 0,
            }
        },
        "data": charges_data,
    }
    requests_mock.get(
        f"https://localhost/v1/billing/journals/{journal_id}/charges", json=response_mock
    )
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.charges(journal_id).all()
    assert result == charges_data


def test_download_charges(requests_mock, mpt_client):
    journal_id = "journal-id"
    csv_content = "id,amount\ncharge-1,100\ncharge-2,200\n"
    url = f"https://localhost/v1/billing/journals/{journal_id}/charges"
    requests_mock.get(
        url, content=csv_content.encode("utf-8"), headers={"Content-Type": "text/csv"}
    )
    api = MPTAPIClient(mpt_client)
    response = api.billing.journal.charges(journal_id).download()
    assert response.content.decode("utf-8") == csv_content
    assert response.headers["Content-Type"] == "text/csv"
