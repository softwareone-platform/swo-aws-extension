import http

import pytest

from swo_aws_extension.swo.mpt.billing.journal_client import JournalClient


@pytest.fixture
def journal_client(mpt_client):
    return JournalClient(mpt_client)


@pytest.fixture
def journal_data():
    return {"id": "journal-id", "name": "test journal"}


def test_list_attachments(requests_mock, journal_client):
    journal_id = "journal-id"
    attachments_data = [{"id": "attachment-1", "filename": "test.pdf"}]
    response_data = {
        "data": attachments_data,
        "$meta": {
            "pagination": {"total": 1, "offset": 0, "limit": 10},
        },
    }
    requests_mock.get(
        f"https://localhost/public/v1/billing/journals/{journal_id}/attachments", json=response_data
    )

    result = journal_client.attachments(journal_id).all()

    assert result == attachments_data


def test_upload_attachment(requests_mock, journal_client, tmp_path):
    journal_id = "journal-id"
    file_content = b"test file content"
    file_path = tmp_path / "test.pdf"
    file_path.write_bytes(file_content)
    response_data = {"id": "attachment-1", "filename": "test.pdf"}
    requests_mock.post(
        f"https://localhost/public/v1/billing/journals/{journal_id}/attachments",
        json=response_data,
        status_code=http.HTTPStatus.CREATED,
    )

    with file_path.open("rb") as file_obj:
        result = journal_client.attachments(journal_id).upload(
            file_obj, "application/pdf", "test.pdf"
        )

    assert result == response_data


def test_get_attachment(requests_mock, journal_client):
    journal_id = "journal-id"
    attachment_id = "attachment-1"
    attachment_data = {"id": attachment_id, "filename": "file1.pdf"}
    requests_mock.get(
        f"https://localhost/public/v1/billing/journals/{journal_id}/attachments/{attachment_id}",
        json=attachment_data,
    )

    result = journal_client.attachments(journal_id).get(attachment_id)

    assert result == attachment_data


def test_delete_attachment(requests_mock, journal_client):
    journal_id = "journal-id"
    attachment_id = "attachment-1"
    requests_mock.delete(
        f"https://localhost/public/v1/billing/journals/{journal_id}/attachments/{attachment_id}",
        status_code=http.HTTPStatus.NO_CONTENT,
    )

    result = journal_client.attachments(journal_id).delete(attachment_id)

    assert result.status_code == http.HTTPStatus.NO_CONTENT


def test_all_charges(requests_mock, journal_client):
    journal_id = "journal-id"
    charges_data = [{"id": "charge-1", "amount": 100}]
    response_mock = {
        "$meta": {
            "pagination": {"total": 1, "offset": 0, "limit": 10},
        },
        "data": charges_data,
    }
    requests_mock.get(
        f"https://localhost/public/v1/billing/journals/{journal_id}/charges", json=response_mock
    )

    result = journal_client.charges(journal_id).all()

    assert result == charges_data


def test_download_charges(requests_mock, journal_client):
    journal_id = "journal-id"
    csv_content = "id,amount\ncharge-1,100\ncharge-2,200\n"
    url = f"https://localhost/public/v1/billing/journals/{journal_id}/charges"
    requests_mock.get(
        url, content=csv_content.encode("utf-8"), headers={"Content-Type": "text/csv"}
    )

    result = journal_client.charges(journal_id).download()

    assert result.content.decode("utf-8") == csv_content
    assert result.headers["Content-Type"] == "text/csv"


def test_get_journal(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.get(
        f"https://localhost/public/v1/billing/journals/{journal_id}", json=journal_data
    )

    result = journal_client.get(journal_id)

    assert result == journal_data


def test_create_journal(requests_mock, journal_client, journal_data):
    requests_mock.post("https://localhost/public/v1/billing/journals", json=journal_data)

    result = journal_client.create(journal_data)

    assert result == journal_data


def test_query_journals(requests_mock, journal_client, journal_data):
    response_data = {
        "$meta": {
            "pagination": {"total": 1, "offset": 0, "limit": 10},
        },
        "data": [journal_data],
    }
    requests_mock.get("https://localhost/public/v1/billing/journals", json=response_data)

    result = journal_client.query("")

    assert result.all() == [journal_data]


def test_all_journals(requests_mock, journal_client, journal_data):
    response_data = {
        "$meta": {
            "pagination": {"total": 1, "offset": 0, "limit": 10},
        },
        "data": [journal_data],
    }
    requests_mock.get("https://localhost/public/v1/billing/journals", json=response_data)

    result = journal_client.all()

    assert result == [journal_data]


def test_update_journal(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.put(
        f"https://localhost/public/v1/billing/journals/{journal_id}", json=journal_data
    )

    result = journal_client.update(journal_id, journal_data)

    assert result == journal_data


def test_upload_journal(requests_mock, journal_client, tmp_path):
    journal_id = "journal-id"
    file_path = tmp_path / "testfile.txt"
    file_path.write_text("test content")
    response_data = {}
    requests_mock.post(
        f"https://localhost/public/v1/billing/journals/{journal_id}/upload",
        json=response_data,
    )

    with file_path.open("rb") as file_obj:
        result = journal_client.upload(journal_id, file_obj)

    assert result == response_data


def test_delete_journal_with_content(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.delete(
        f"https://localhost/public/v1/billing/journals/{journal_id}", json=journal_data
    )

    result = journal_client.delete(journal_id)

    assert result == journal_data


def test_delete_journal_no_content(requests_mock, journal_client):
    journal_id = "journal-id"
    requests_mock.delete(f"https://localhost/public/v1/billing/journals/{journal_id}", text="")

    result = journal_client.delete(journal_id)

    assert result is None


def test_regenerate_journal(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.post(
        f"https://localhost/public/v1/billing/journals/{journal_id}/regenerate", json=journal_data
    )

    result = journal_client.regenerate(journal_id)

    assert result == journal_data


def test_accept_journal(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.post(
        f"https://localhost/public/v1/billing/journals/{journal_id}/accept",
        json=journal_data,
    )

    result = journal_client.accept(journal_id)

    assert result == journal_data


def test_submit_journal(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.post(
        f"https://localhost/public/v1/billing/journals/{journal_id}/submit",
        json=journal_data,
    )

    result = journal_client.submit(journal_id)

    assert result == journal_data


def test_inquire_journal(requests_mock, journal_client, journal_data):
    journal_id = "journal-id"
    requests_mock.post(
        f"https://localhost/public/v1/billing/journals/{journal_id}/inquire",
        json=journal_data,
    )

    result = journal_client.inquire(journal_id)

    assert result == journal_data
