from swo_mpt_api import MPTAPIClient


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
