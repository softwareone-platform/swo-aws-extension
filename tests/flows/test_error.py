import pytest

from swo_aws_extension.flows import error as flow_errors


@pytest.mark.parametrize(
    ("needle", "should_be_present"),
    [
        ("(<omitted>)", True),
        ("00-0123456789abcdef0123456789abcdef-0123456789abcdef-01", False),
        ("00-ffffffffffffffffffffffffffffffff-aaaaaaaaaaaaaaaa-01", False),
    ],
)
def test_strip_trace_id_parametrized(needle, should_be_present):
    error_msg = (
        "Error (00-0123456789abcdef0123456789abcdef-0123456789abcdef-01) happened; "
        "again (00-ffffffffffffffffffffffffffffffff-aaaaaaaaaaaaaaaa-01)."
    )

    out_msg = flow_errors.strip_trace_id(error_msg)

    assert (needle in out_msg) is should_be_present
