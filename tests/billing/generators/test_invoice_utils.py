import pytest

from swo_aws_extension.billing.generators.invoice_utils import merge_invoice_ids


@pytest.mark.parametrize(
    ("existing_id", "new_id", "expected"),
    [
        ("2609293185", "", "2609293185"),
        ("2609293185", "SGIN26-350441", "-3185,-0441"),
        ("-3185,-0441", "EUINPL26-355205", "-3185,-0441,-5205"),
        ("-3185,-0441,-5205", "NEXT26-000002", "-3185,-0441,-5205,.."),
        ("-3185,-0441,-5205,..", "NEXT26-000003", "-3185,-0441,-5205,.."),
    ],
)
def test_merge_invoice_ids(existing_id, new_id, expected):
    result = merge_invoice_ids(existing_id, new_id)  # act

    assert result == expected
