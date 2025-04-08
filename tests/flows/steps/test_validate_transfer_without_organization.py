from swo_aws_extension.flows.steps.validate import is_list_of_aws_accounts


def test_validate_account_id():
    # Test with valid account IDs
    valid_account_ids = "123456789012\n123456789013"
    assert (
        is_list_of_aws_accounts(valid_account_ids) is True
    ), "Two 12 digits separated by new line is a valid list of accounts"

    # Additional \n should be considered
    invalid_account_ids = "123456789012\n\n123456789013\n"
    assert (
        is_list_of_aws_accounts(invalid_account_ids) is True
    ), "Accept multiple new lines (including empty and trailing new lines)"

    # Only numeric digits are valid
    invalid_account_ids = "12345678901A\n123456789013"
    assert (
        is_list_of_aws_accounts(invalid_account_ids) is False
    ), "Account IDs does not have letters"

    # Test with a 13-digit account ID
    invalid_account_ids = "12345678901\n1234567890134"
    assert is_list_of_aws_accounts(invalid_account_ids) is False, "13 digits account ID is invalid"

    # Test with empty account IDs
    empty_account_ids = ""
    assert is_list_of_aws_accounts(empty_account_ids) is False

    # Test with None account IDs
    none_account_ids = None
    assert is_list_of_aws_accounts(none_account_ids) is False
