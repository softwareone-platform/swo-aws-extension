from decimal import Decimal

from swo_aws_extension.shared import find_first_match


def test_find_first_match_found():
    dict_data = {"a": Decimal("1.0"), "b": Decimal("2.0")}

    first_match = find_first_match(dict_data, "a", Decimal("1.0"))

    assert first_match == {"a": Decimal("1.0")}


def test_find_first_match_not_found():
    dict_data = {"a": Decimal("1.0"), "b": Decimal("2.0")}

    first_match = find_first_match(dict_data, "c", Decimal("3.0"))

    assert first_match is None
