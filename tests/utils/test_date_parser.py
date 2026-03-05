import datetime as dt

from swo_aws_extension.utils import date_parser

NAIVE_DT_STR = "2024-06-15T10:30:00"
UTC_DT_STR = "2024-06-15T10:30:00+00:00"
EST_DT_STR = "2024-06-15T10:30:00-05:00"
EST_IN_UTC_STR = "2024-06-15T15:30:00+00:00"
DT_WITH_MICROSECONDS_STR = "2024-06-15T10:30:00.123456"
DT_WITH_SMALL_MS_STR = "2024-06-15T10:30:00.001000"
DT_WITH_ZERO_MS_STR = "2024-06-15T00:00:00.000000"


def test_to_utc_naive_datetime_gets_utc_timezone():
    naive = dt.datetime.fromisoformat(NAIVE_DT_STR)

    result = date_parser.to_utc(naive)

    assert result.tzinfo == dt.UTC
    assert result == dt.datetime.fromisoformat(UTC_DT_STR)


def test_to_utc_utc_datetime_unchanged():
    utc_dt = dt.datetime.fromisoformat(UTC_DT_STR)

    result = date_parser.to_utc(utc_dt)

    assert result == utc_dt


def test_to_utc_non_utc_timezone_converted():
    est_dt = dt.datetime.fromisoformat(EST_DT_STR)

    result = date_parser.to_utc(est_dt)

    assert result.tzinfo == dt.UTC
    assert result == dt.datetime.fromisoformat(EST_IN_UTC_STR)


def test_format_date_empty_string_returns_empty():
    date_str = ""

    result = date_parser.to_str(date_str)

    assert not result


def test_format_date_iso_string_without_timezone():
    result = date_parser.to_str(NAIVE_DT_STR)

    assert result == "2024-06-15 10:30:00.000"


def test_format_date_iso_string_with_utc_offset():
    result = date_parser.to_str(UTC_DT_STR)

    assert result == "2024-06-15 10:30:00.000"


def test_format_date_non_utc_offset_converts_to_utc():
    result = date_parser.to_str(EST_DT_STR)

    assert result == "2024-06-15 15:30:00.000"


def test_format_date_microseconds_truncated_to_milliseconds():
    result = date_parser.to_str(DT_WITH_MICROSECONDS_STR)

    assert result == "2024-06-15 10:30:00.123"


def test_format_date_milliseconds_padded_to_three_digits():
    result = date_parser.to_str(DT_WITH_SMALL_MS_STR)

    assert result == "2024-06-15 10:30:00.001"


def test_format_date_zero_microseconds_formats_correctly():
    result = date_parser.to_str(DT_WITH_ZERO_MS_STR)

    assert result == "2024-06-15 00:00:00.000"
