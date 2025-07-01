import pytest
import responses

from swo_mpt_api import MPTAPIClient
from swo_mpt_api.models.hints import Journal


@pytest.fixture()
def journal_data():
    return Journal(
        name="Test Journal",
    )


@responses.activate
def test_get_journal_charges(mpt_client, journal_data):
    journal_id = "journal-id"

    responses.get(f"https://localhost/v1/billing/journals/{journal_id}", json=journal_data)
    api = MPTAPIClient(mpt_client)
    journal = api.billing.journal.get(journal_id)
    assert journal == journal_data


@responses.activate
def test_create_journal(mpt_client, journal_data):
    responses.post("https://localhost/v1/billing/journals", json=journal_data)
    api = MPTAPIClient(mpt_client)
    journal = api.billing.journal.create(journal_data)
    assert journal == journal_data


@responses.activate
def test_query_journals(mpt_client, journal_data):
    response_data = {
        "$meta": {
            "pagination": {
                "total": 1,
                "limit": 10,
                "offset": 0,
            }
        },
        "data": [journal_data],
    }
    responses.get("https://localhost/v1/billing/journals", json=response_data)
    api = MPTAPIClient(mpt_client)
    journals = api.billing.journal.query("")
    assert journals.all() == [journal_data]


@responses.activate
def test_update_journal(mpt_client, journal_data):
    journal_id = "journal-id"
    responses.put(f"https://localhost/v1/billing/journals/{journal_id}", json=journal_data)
    api = MPTAPIClient(mpt_client)
    updated_journal = api.billing.journal.update(journal_id, journal_data)
    assert updated_journal == journal_data


@responses.activate
def test_upload_journal(mpt_client, journal_data, tmp_path):
    journal_id = "journal-id"
    file_path = tmp_path / "testfile.txt"
    file_path.write_text("test content")

    response_data = {}

    responses.post(f"https://localhost/v1/billing/journals/{journal_id}/upload", json=response_data)

    api = MPTAPIClient(mpt_client)
    with file_path.open("rb") as f:
        result = api.billing.journal.upload(journal_id, f)
    assert result == response_data


@responses.activate
def test_delete_journal(mpt_client):
    journal_id = "journal-id"
    response_data = None
    responses.delete(f"https://localhost/v1/billing/journals/{journal_id}", json=response_data)
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.delete(journal_id)
    assert result == response_data


@responses.activate
def test_regenerate_journal(mpt_client, journal_data):
    journal_id = "journal-id"
    response_data = journal_data
    responses.post(
        f"https://localhost/v1/billing/journals/{journal_id}/regenerate", json=response_data
    )
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.regenerate(journal_id)
    assert result == response_data


@responses.activate
def test_accept_journal(mpt_client, journal_data):
    journal_id = "journal-id"
    response_data = journal_data
    responses.post(f"https://localhost/v1/billing/journals/{journal_id}/accept", json=response_data)
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.accept(journal_id)
    assert result == response_data


@responses.activate
def test_submit_journal(mpt_client, journal_data):
    journal_id = "journal-id"
    response_data = journal_data
    responses.post(f"https://localhost/v1/billing/journals/{journal_id}/submit", json=response_data)
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.submit(journal_id)
    assert result == response_data


@responses.activate
def test_inquire_journal(mpt_client, journal_data):
    journal_id = "journal-id"
    responses.post(f"https://localhost/v1/billing/journals/{journal_id}/inquire", json=journal_data)
    api = MPTAPIClient(mpt_client)
    result = api.billing.journal.inquire(journal_id)
    assert result == journal_data
