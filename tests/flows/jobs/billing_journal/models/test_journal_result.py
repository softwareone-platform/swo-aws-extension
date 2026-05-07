import pytest

from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import PlsMismatch


@pytest.mark.parametrize(
    ("pls_in_order", "report_has_enterprise", "expected"),
    [
        (
            True,
            True,
            "Agreement AGR-1: parameter=PLS but report has 'AWS Support (Enterprise)'.",
        ),
        (
            True,
            False,
            "Agreement AGR-1: parameter=PLS but report does not have 'AWS Support (Enterprise)'.",
        ),
        (
            False,
            True,
            "Agreement AGR-1: parameter=Resold Support but report has 'AWS Support (Enterprise)'.",
        ),
        (
            False,
            False,
            (
                "Agreement AGR-1: parameter=Resold Support but report does not have 'AWS Support "
                "(Enterprise)'."
            ),
        ),
    ],
)
def test_pls_mismatch_description(pls_in_order, report_has_enterprise, expected):
    result = PlsMismatch(
        agreement_id="AGR-1",
        pls_in_order=pls_in_order,
        report_has_enterprise=report_has_enterprise,
    )

    assert result.description == expected
