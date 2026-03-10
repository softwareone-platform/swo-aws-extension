from swo_aws_extension.flows.jobs.billing_journal.models.journal import Journal


def test_from_dict():
    payload = {"id": "JRN-456", "name": "Oct Journal", "status": "Processing"}

    result = Journal.from_dict(payload)

    assert result.id == "JRN-456"
    assert result.name == "Oct Journal"
    assert result.status == "Processing"


def test_from_dict_with_missing_fields():
    payload = {"id": "JRN-789"}

    result = Journal.from_dict(payload)

    assert result.id == "JRN-789"
    assert result.name is None
    assert result.status is None
